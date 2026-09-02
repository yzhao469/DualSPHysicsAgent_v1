"""PlanAndBuildExecutor — planning, build pipeline, and setup review.

Merges the former PlanningExecutor, BuildExecutor, and SetupReviewExecutor
into a single executor. Handles:
  1. Wrapping scenario/revision into AgentExecutorRequest
  2. Running the deterministic build pipeline from the agent's plan
  3. LLM tool-use review loop for plan + viz
"""

import base64
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from openai import AsyncOpenAI

from agent_framework import (
    AgentExecutorRequest,
    AgentExecutorResponse,
    Content,
    Executor,
    MCPStdioTool,
    Message,
    WorkflowContext,
    handler,
    response_handler,
)

from agents.schemas import (
    PhysicsParams,
    ReviewResult,
    SetupReviewRequest,
    SimulationPlan,
)
from agents.tools.visualize_geometry import visualize_geometry
from agents.utils.build_utils import rebuild_gencase_viz
from agents.utils.chat_logger import log_message
from agents.utils.context_trimmer import trim_chat_completions_history
from agents.utils.intent import answer_question, resolve_datalake_files
from agents.utils.mcp_tools import (
    BUILD_DIAGNOSTICS,
    check_mcp_tool_result,
    diagnose_error,
)
from agents.utils.patch_utils import generate_patch, merge_patch
from agents.utils.skill_loader import get_skill_topic

from agents.executors._setup_review import (
    MAX_BUILD_RECOVERY_ATTEMPTS,
    TOOLS,
    build_instructions,
    format_plan_summary,
    is_image_file,
    is_mesh_file,
    list_datalake_files,
    system_message,
    tool_result,
    user_message,
    user_message_with_images,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Executor
# ─────────────────────────────────────────────────────────────────────────────


class PlanAndBuildExecutor(Executor):
    """Plans, builds, and reviews the simulation setup."""

    def __init__(self, mcp: MCPStdioTool, base_dir: str) -> None:
        super().__init__(id="plan_and_build")
        self.mcp = mcp
        self.base_dir = base_dir

    # ── Planning handlers ────────────────────────────────────────────────

    _DRAW_COMMANDS = {
        ".stl": "drawfilestl",
        ".vtk": "drawfilevtk",
        ".ply": "drawfileply",
        ".csv": "drawfilecsv",
    }

    def _build_datalake_message(
        self, scenario: str, matched_files: list[str], ctx: WorkflowContext,
    ) -> Message:
        """Build a single multimodal Message from all matched datalake files.

        Combines scenario text, XML content, mesh file references, and images
        into one planner message.
        """
        text_parts: list[str] = [scenario]
        image_contents: list[Content] = []
        mesh_paths: list[str] = []
        image_rel_paths: list[str] = []

        for rel_path in matched_files:
            abs_path = Path(self.base_dir) / rel_path

            if is_mesh_file(abs_path):
                filename = abs_path.name
                draw_cmd = self._DRAW_COMMANDS[abs_path.suffix.lower()]
                mesh_paths.append(str(abs_path))
                text_parts.append(
                    f"### Available Mesh File ({rel_path})\n"
                    f"A mesh file `{filename}` will be copied to the run directory. "
                    f"Use `<{draw_cmd} file=\"{filename}\">` in your geometry XML to import it. "
                    "You can apply transforms (drawmove, drawrotate, drawscale) inside the element."
                )
                logger.info("PlanAndBuildExecutor: injected datalake mesh %s", abs_path)

            elif is_image_file(abs_path):
                suffix = abs_path.suffix.lower()
                media_type = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}[suffix]
                image_contents.append(Content.from_data(abs_path.read_bytes(), media_type))
                image_rel_paths.append(rel_path)
                text_parts.append(
                    f"### Reference Image ({rel_path})\n"
                    "The attached image shows the target geometry. Study it carefully and "
                    "create DualSPHysics XML geometry that reproduces this configuration. "
                    "Pay attention to dimensions, shapes, positions, and boundaries."
                )
                logger.info("PlanAndBuildExecutor: injected datalake image %s", abs_path)

            else:  # XML
                xml_content = abs_path.read_text()
                ctx.set_state("base_xml", str(abs_path))
                text_parts.append(
                    f"### Existing Case XML ({rel_path})\n"
                    f"```xml\n{xml_content}\n```\n\n"
                    "Modify this existing case according to the user's instructions. "
                    "You may reuse or adjust the geometry, parameters, and probe points."
                )
                logger.info("PlanAndBuildExecutor: injected datalake XML %s", abs_path)

        # Store paths for later use
        if mesh_paths:
            ctx.set_state("datalake_mesh_paths", mesh_paths)
        if image_rel_paths:
            ctx.set_state("datalake_image_paths", image_rel_paths)
        # Store all matched files for the review datalake retrieval tool
        ctx.set_state("datalake_matched_files", matched_files)

        # Build message: text + images as multimodal content
        combined_text = "\n\n".join(text_parts)
        if image_contents:
            return Message("user", [combined_text, *image_contents])
        return Message("user", [combined_text])

    @handler
    async def start(self, scenario: str, ctx: WorkflowContext[AgentExecutorRequest | ReviewResult]) -> None:
        """Initial entry: receive a natural-language scenario."""
        logger.info("PlanAndBuildExecutor: new scenario (%d chars)", len(scenario))
        ctx.set_state("scenario", scenario)

        available = list_datalake_files(self.base_dir)
        matched = await resolve_datalake_files(scenario, available) if available else []

        if matched:
            msg = self._build_datalake_message(scenario, matched, ctx)
        else:
            msg = Message("user", [scenario])

        await ctx.send_message(AgentExecutorRequest(messages=[msg], should_respond=True))

    @handler
    async def on_revision(self, review: ReviewResult, ctx: WorkflowContext[AgentExecutorRequest | ReviewResult]) -> None:
        """Full replan: the user wants to start over with a different scenario."""
        plan_data = ctx.get_state("plan")
        text = f"Please revise the simulation: {review.feedback}"
        if plan_data:
            text += f"\n\n### Previous Plan\n```json\n{json.dumps(plan_data, indent=2)}\n```"
        logger.info("PlanAndBuildExecutor: revision request — %s", review.feedback)
        msg = Message("user", [text])
        await ctx.send_message(AgentExecutorRequest(messages=[msg], should_respond=True))

    # ── Build + review init ──────────────────────────────────────────────

    def _new_run_dir(self) -> str:
        """Create a timestamped run directory path for the current build."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"{self.base_dir}/runs/run_{ts}"

    async def _build(self, plan_data: dict, base_xml: str, run_dir: str, ctx: WorkflowContext) -> str:
        """set_geometry -> modify_xml -> run_gencase -> visualize."""
        geometry_xml: str = plan_data["geometry_xml"]
        params = PhysicsParams(**plan_data["params"])

        Path(run_dir).mkdir(parents=True, exist_ok=True)
        case_xml = f"{run_dir}/Case_Def.xml"

        # 0. Copy mesh files to run directory (if provided via datalake)
        for mesh_src in ctx.get_state("datalake_mesh_paths") or []:
            if Path(mesh_src).exists():
                dest = Path(run_dir) / Path(mesh_src).name
                shutil.copy2(mesh_src, dest)
                logger.info("Copied mesh file %s -> %s", mesh_src, dest)

        # 1. Set geometry
        logger.info(">>> set_geometry")
        r = await self.mcp.call_tool(
            "set_geometry",
            base_xml=base_xml,
            output_xml=case_xml,
            geometry_xml=geometry_xml,
        )
        check_mcp_tool_result("set_geometry", r)
        logger.info("set_geometry OK")

        # 2. Modify physics parameters
        logger.info(">>> modify_xml")
        r = await self.mcp.call_tool(
            "modify_xml",
            base_xml=case_xml,
            output_xml=case_xml,
            **params.model_dump(),
        )
        check_mcp_tool_result("modify_xml", r)
        logger.info("modify_xml OK: %s", r)

        # 3. Run GenCase
        logger.info(">>> run_gencase")
        r = await self.mcp.call_tool(
            "run_gencase",
            xml_path=f"{run_dir}/Case_Def",  # no .xml extension
            output_dir=f"{run_dir}/out",
        )
        check_mcp_tool_result("run_gencase", r)
        logger.info("run_gencase OK")

        # 5. Visualize (direct Python call, not MCP)
        logger.info(">>> visualize_geometry")
        viz_result = visualize_geometry(f"{run_dir}/out")
        logger.info("visualize_geometry: %s", viz_result)

        return run_dir

    @handler
    async def on_plan(self, result: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest | ReviewResult]) -> None:
        """Parse the agent's SimulationPlan, build, then start setup review."""
        raw_text = result.agent_response.text
        logger.info("PlanAndBuildExecutor: agent response length: %d chars", len(raw_text))

        plan = SimulationPlan.model_validate_json(raw_text)
        plan_data = plan.model_dump()
        ctx.set_state("plan", plan_data)

        base_xml = ctx.get_state("base_xml") or f"{self.base_dir}/cases/BaseCase_Def.xml"
        run_dir = self._new_run_dir()
        ctx.set_state("run_dir", run_dir)

        # Log the initial scenario now that run_dir exists
        scenario = ctx.get_state("scenario") or ""
        if scenario:
            log_message(run_dir, "user", scenario, phase="planning")

        # Log any datalake input images/meshes so the HTML report can embed them
        for rel in ctx.get_state("datalake_image_paths") or []:
            log_message(run_dir, "user", f"[input-image] {rel}", phase="planning")
        for abs_mesh in ctx.get_state("datalake_mesh_paths") or []:
            log_message(run_dir, "user", f"[input-mesh] {abs_mesh}", phase="planning")

        # Run build pipeline
        build_error: str | None = None
        try:
            await self._build(plan_data, base_xml, run_dir, ctx)
        except Exception as exc:
            logger.exception("Build pipeline failed")
            build_error = str(exc)

        # Build plan summary
        summary = format_plan_summary(plan)
        if build_error:
            diagnostics = diagnose_error(build_error, BUILD_DIAGNOSTICS)
            logger.warning("Build failed: %s — entering setup review recovery loop", build_error)
            summary = (
                f"{summary}\n\n"
                "Build failed before the setup could be reviewed.\n"
                f"Error:\n{build_error}\n\n"
                f"Possible causes:\n{diagnostics}\n\n"
                "You can request a fix, manually edit the XML, ask a question, or replan."
            )

        # Initialize review state
        if build_error:
            self._set_recovery_state(ctx, build_error, retry_count=0)
        else:
            self._set_recovery_state(ctx)
        self._refresh_instructions(ctx, plan_data, run_dir)

        # Initialize conversation history (Chat Completions API format)
        history: list[dict] = []
        ctx.set_state("setup_review_history", history)

        log_message(run_dir, "assistant", summary, phase="setup_review")
        await ctx.request_info(
            request_data=SetupReviewRequest(summary=summary),
            response_type=str,
        )

    # ── Recovery state helpers ───────────────────────────────────────────

    @staticmethod
    def _set_recovery_state(
        ctx: WorkflowContext,
        error_message: str | None = None,
        retry_count: int = 0,
    ) -> None:
        ctx.set_state("setup_review_retry_count", retry_count)
        ctx.set_state("setup_review_last_error", error_message)

    @staticmethod
    def _record_recovery_failure(ctx: WorkflowContext, error_message: str) -> int:
        retry_count = (ctx.get_state("setup_review_retry_count") or 0) + 1
        PlanAndBuildExecutor._set_recovery_state(ctx, error_message, retry_count)
        return retry_count

    @staticmethod
    def _refresh_instructions(
        ctx: WorkflowContext,
        plan_data: dict,
        run_dir: str,
    ) -> str:
        """Rebuild and store the review LLM instructions (used as system message)."""
        matched_files = ctx.get_state("datalake_matched_files") or []
        datalake_names = [Path(p).name for p in matched_files]
        instructions = build_instructions(
            plan_data,
            run_dir,
            build_error=ctx.get_state("setup_review_last_error"),
            retry_count=ctx.get_state("setup_review_retry_count") or 0,
            datalake_files=datalake_names or None,
        )
        ctx.set_state("setup_review_instructions", instructions)
        return instructions

    # ── Setup review HITL loop ───────────────────────────────────────────

    @response_handler
    async def on_user_reply(
        self,
        request: SetupReviewRequest,
        feedback: str,
        ctx: WorkflowContext[AgentExecutorRequest | ReviewResult],
    ) -> None:
        """Process user reply through the LLM tool-use loop (Chat Completions API)."""
        history = ctx.get_state("setup_review_history") or []
        instructions = ctx.get_state("setup_review_instructions") or ""
        plan_data = ctx.get_state("plan")
        run_dir = ctx.get_state("run_dir")

        # Check if we're resuming after a sim confirmation prompt
        pending_sim_confirm = ctx.get_state("pending_sim_confirm")
        if pending_sim_confirm:
            ctx.set_state("pending_sim_confirm", False)
            confirmed = feedback.strip().lower() in ("yes", "y", "confirm", "run", "ok", "go", "")
            if confirmed:
                ctx.set_state("setup_review_history", history)
                await ctx.send_message(
                    ReviewResult(route="sim", feedback="approved")
                )
                return
            history.append(user_message(feedback or "no"))
            log_message(run_dir, "user", feedback or "no", phase="setup_review")

        # Check if we're resuming after a manual edit pause
        pending_manual_edit = ctx.get_state("pending_manual_edit")
        if pending_manual_edit:
            ctx.set_state("pending_manual_edit", False)
            try:
                await rebuild_gencase_viz(self.mcp, run_dir)
                self._set_recovery_state(ctx)
                instructions = self._refresh_instructions(ctx, plan_data, run_dir)
                history.append(tool_result(
                    pending_manual_edit,
                    "Manual edit complete. GenCase rebuilt and visualization regenerated.",
                ))
            except Exception as exc:
                logger.exception("Manual edit rebuild failed")
                retry_count = self._record_recovery_failure(ctx, str(exc))
                instructions = self._refresh_instructions(ctx, plan_data, run_dir)
                history.append(tool_result(
                    pending_manual_edit,
                    f"Rebuild failed: {exc}",
                ))
                if retry_count >= MAX_BUILD_RECOVERY_ATTEMPTS:
                    ctx.set_state("setup_review_history", history)
                    await ctx.send_message(
                        ReviewResult(
                            route="full_replan",
                            feedback=(
                                "Build recovery failed repeatedly after manual edits. "
                                f"Last error: {exc}"
                            ),
                        )
                    )
                    return
        else:
            history.append(user_message(feedback or "approve"))
            log_message(run_dir, "user", feedback or "approve", phase="setup_review")

        client = AsyncOpenAI()

        while True:
            # Trim older entries to prevent unbounded context growth
            trim_chat_completions_history(history)

            # Build messages list: system message + conversation history
            messages = [system_message(instructions)] + history

            response = await client.chat.completions.create(
                model=os.getenv("INTENT_MODEL", "gpt-4o-mini"),
                temperature=0,
                messages=messages,
                tools=TOOLS,
            )

            choice = response.choices[0]
            msg = choice.message

            # Add the full assistant message to history
            history.append(msg.model_dump(exclude_none=True))

            assistant_text = msg.content or ""

            if not msg.tool_calls:
                # Pure text response — send to user
                ctx.set_state("setup_review_history", history)
                log_message(run_dir, "assistant", assistant_text, phase="setup_review")
                await ctx.request_info(
                    request_data=SetupReviewRequest(summary=assistant_text),
                    response_type=str,
                )
                return

            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)

                if fn_name == "approve":
                    last_error = ctx.get_state("setup_review_last_error")
                    if last_error:
                        history.append(tool_result(
                            tc.id,
                            "Cannot approve yet because the current setup still has an "
                            f"unresolved build error: {last_error}. "
                            "Fix it first with `patch_and_rebuild`, `manual_edit`, or `replan`.",
                        ))
                        continue
                    history.append(tool_result(
                        tc.id,
                        "Waiting for user confirmation to proceed.",
                    ))
                    ctx.set_state("setup_review_history", history)
                    ctx.set_state("pending_sim_confirm", True)
                    await ctx.request_info(
                        request_data=SetupReviewRequest(
                            summary="Ready to run the main simulation. Confirm?",
                            confirm_sim=True,
                        ),
                        response_type=str,
                    )
                    return

                elif fn_name == "replan":
                    ctx.set_state("setup_review_history", history)
                    await ctx.send_message(
                        ReviewResult(
                            route="full_replan",
                            feedback=fn_args.get("new_scenario", feedback),
                        )
                    )
                    return

                elif fn_name == "patch_and_rebuild":
                    changes = fn_args["changes"]
                    try:
                        result_text = await self._patch_and_rebuild(
                            changes, plan_data, run_dir, ctx
                        )
                        self._set_recovery_state(ctx)
                        instructions = self._refresh_instructions(ctx, plan_data, run_dir)
                        history.append(tool_result(tc.id, result_text))
                    except Exception as exc:
                        logger.exception("patch_and_rebuild failed")
                        retry_count = self._record_recovery_failure(ctx, str(exc))
                        instructions = self._refresh_instructions(ctx, plan_data, run_dir)
                        history.append(tool_result(tc.id, f"Error: {exc}"))
                        if retry_count >= MAX_BUILD_RECOVERY_ATTEMPTS:
                            ctx.set_state("setup_review_history", history)
                            await ctx.send_message(
                                ReviewResult(
                                    route="full_replan",
                                    feedback=(
                                        "Build recovery failed repeatedly during setup review. "
                                        f"Last error: {exc}"
                                    ),
                                )
                            )
                            return

                elif fn_name == "manual_edit":
                    case_xml = f"{run_dir}/Case_Def.xml"
                    ctx.set_state("setup_review_history", history)
                    ctx.set_state("pending_manual_edit", tc.id)
                    await ctx.request_info(
                        request_data=SetupReviewRequest(
                            summary=(
                                f"Edit the case file at:\n  {case_xml}\n\n"
                                "Type 'done' when finished editing."
                            ),
                        ),
                        response_type=str,
                    )
                    return

                elif fn_name == "get_reference":
                    topic = fn_args["topic"]
                    ref_content = get_skill_topic(topic)
                    history.append(tool_result(tc.id, ref_content))

                elif fn_name == "answer_question":
                    question = fn_args["question"]
                    plan_context = json.dumps(plan_data, indent=2)
                    answer = await answer_question(question, plan_context)
                    history.append(tool_result(tc.id, answer))

                elif fn_name == "view_datalake_file":
                    filename = fn_args["filename"]
                    matched_files_list = ctx.get_state("datalake_matched_files") or []
                    # Find matching file
                    matched_path = None
                    for rel_path in matched_files_list:
                        if Path(rel_path).name == filename:
                            matched_path = Path(self.base_dir) / rel_path
                            break
                    if matched_path and matched_path.exists():
                        if is_image_file(matched_path):
                            suffix = matched_path.suffix.lower()
                            media_type = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}[suffix]
                            img_b64 = base64.b64encode(matched_path.read_bytes()).decode()
                            history.append(user_message_with_images(
                                f"Reference image: {filename}",
                                [(img_b64, media_type)],
                            ))
                            history.append(tool_result(tc.id, f"Image '{filename}' is now visible above."))
                        else:
                            content = matched_path.read_text(errors="replace")
                            ext = matched_path.suffix.lower().lstrip(".")
                            history.append(tool_result(
                                tc.id,
                                f"Contents of {filename}:\n```{ext}\n{content}\n```",
                            ))
                    else:
                        available = [Path(p).name for p in matched_files_list]
                        history.append(tool_result(
                            tc.id,
                            f"File '{filename}' not found. Available: {', '.join(available) or 'none'}",
                        ))

            ctx.set_state("setup_review_history", history)

    async def _patch_and_rebuild(
        self,
        changes: str,
        plan_data: dict,
        run_dir: str,
        ctx: WorkflowContext,
    ) -> str:
        """Apply LLM patch, rebuild gencase, regenerate visualization."""
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        case_xml = f"{run_dir}/Case_Def.xml"
        if Path(case_xml).exists():
            current_xml = Path(case_xml).read_text()
        else:
            base_xml = ctx.get_state("base_xml") or f"{self.base_dir}/cases/BaseCase_Def.xml"
            current_xml = Path(base_xml).read_text()

        patch = await generate_patch(current_xml, plan_data, changes)
        logger.info("LLM patch keys: %s", list(patch.keys()))

        if "geometry_xml" in patch:
            logger.info(">>> set_geometry (patch)")
            r = await self.mcp.call_tool(
                "set_geometry",
                base_xml=case_xml,
                output_xml=case_xml,
                geometry_xml=patch["geometry_xml"],
            )
            check_mcp_tool_result("set_geometry", r)

        if "params" in patch:
            logger.info(">>> modify_xml (patch)")
            merged_params = {**plan_data["params"], **patch["params"]}
            r = await self.mcp.call_tool(
                "modify_xml",
                base_xml=case_xml,
                output_xml=case_xml,
                **merged_params,
            )
            check_mcp_tool_result("modify_xml", r)

        merge_patch(plan_data, patch)
        ctx.set_state("plan", plan_data)

        await rebuild_gencase_viz(self.mcp, run_dir)

        return "Patch applied successfully. Visualization regenerated with the updated geometry."
