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
from agents.utils.intent import answer_question, resolve_datalake_file
from agents.utils.patch_utils import generate_patch, merge_patch
from agents.utils.skill_loader import get_skill_content, get_skill_topic

logger = logging.getLogger(__name__)
MAX_BUILD_RECOVERY_ATTEMPTS = 3

# ─────────────────────────────────────────────────────────────────────────────
# OpenAI function definitions for the setup review LLM (Responses API format)
# ─────────────────────────────────────────────────────────────────────────────

_TOOLS = [
    {
        "type": "function",
        "name": "patch_and_rebuild",
        "description": (
            "Apply changes to the simulation case XML based on the user's "
            "description. Re-runs GenCase and regenerates the visualization."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "changes": {
                    "type": "string",
                    "description": "Description of what to change in the simulation setup.",
                },
            },
            "required": ["changes"],
        },
    },
    {
        "type": "function",
        "name": "answer_question",
        "description": (
            "Answer a question about the simulation plan, physics, "
            "DualSPHysics, or the current setup."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to answer.",
                },
            },
            "required": ["question"],
        },
    },
    {
        "type": "function",
        "name": "approve",
        "description": "User is satisfied with the setup. Proceed to simulation.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "manual_edit",
        "description": (
            "Let the user manually edit the Case_Def.xml file directly. "
            "Use this when the user says they want to edit the file themselves."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "get_reference",
        "description": (
            "Fetch detailed reference for a specific XML/geometry topic. "
            "Use this when you need exact syntax, drawing primitives, "
            "transform rules, or composition examples."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": [
                        "xml-overview",
                        "drawing-shapes",
                        "fill-and-modification",
                        "transforms-and-variables",
                        "composition-patterns",
                    ],
                    "description": "Which reference to fetch.",
                },
            },
            "required": ["topic"],
        },
    },
    {
        "type": "function",
        "name": "replan",
        "description": (
            "Scrap the current plan and start over with a different scenario."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "new_scenario": {
                    "type": "string",
                    "description": "The new scenario description.",
                },
            },
            "required": ["new_scenario"],
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


_DATALAKE_EXTENSIONS = {".xml", ".png", ".jpg", ".jpeg"}


def _list_datalake_files(base_dir: str) -> list[str]:
    """Return relative paths of all XML and image files in the datalake directory."""
    datalake = Path(base_dir) / "datalake"
    if not datalake.is_dir():
        return []
    return sorted(
        str(p.relative_to(base_dir))
        for p in datalake.rglob("*")
        if p.suffix.lower() in _DATALAKE_EXTENSIONS
    )


def _is_image_file(path: Path) -> bool:
    return path.suffix.lower() in {".png", ".jpg", ".jpeg"}


def _build_instructions(
    plan_data: dict,
    run_dir: str,
    build_error: str | None = None,
    retry_count: int = 0,
    max_retry_count: int = MAX_BUILD_RECOVERY_ATTEMPTS,
) -> str:
    """Build the instructions for the setup review LLM."""
    plan_summary = json.dumps(plan_data, indent=2)
    build_status = (
        "Build failed before review started."
        if build_error
        else "Build completed successfully."
    )
    failure_guidance = ""
    if build_error:
        failure_guidance = (
            f"### Current Build Error\n{build_error}\n\n"
            f"### Recovery Attempts\n{retry_count} of {max_retry_count}\n\n"
        )
    return (
        "You are a helpful assistant reviewing a DualSPHysics simulation setup. "
        "The user has been shown the simulation plan and a visualization "
        "of the particle geometry.\n\n"
        f"### Build Status\n{build_status}\n\n"
        f"{failure_guidance}"
        f"### Current Simulation Plan\n```json\n{plan_summary}\n```\n\n"
        f"### Run Directory\n{run_dir}\n\n"
        "### Your Role\n"
        "- If the build status is failed, do not call `approve` until the setup has been rebuilt successfully.\n"
        "- If the user is happy with the setup, call `approve` to proceed to simulation.\n"
        "- If the user wants changes (geometry, parameters, probes), call `patch_and_rebuild`.\n"
        "- If the user wants to edit the XML file themselves, call `manual_edit`.\n"
        "- If the user asks a question, call `answer_question`.\n"
        "- If the user wants to start over entirely, call `replan`.\n"
        f"- If recovery keeps failing and you have already used {max_retry_count} rebuild attempts, call `replan`.\n"
        "- Always be concise and helpful.\n"
        "- When the user gives short affirmative responses like 'yes', 'ok', 'looks good', "
        "'go ahead', 'proceed', or just presses Enter, call `approve`.\n"
    )


def _format_plan_summary(plan: SimulationPlan) -> str:
    """Build a human-readable summary of the simulation plan."""
    lines = [
        "=" * 64,
        "  SIMULATION PLAN",
        "=" * 64,
        "",
        "### Reasoning",
        plan.reasoning,
        "",
    ]
    if plan.geometry_xml:
        lines += [
            "### Geometry XML",
            "```xml",
            plan.geometry_xml,
            "```",
            "",
        ]
    lines.append("### Physics Parameters")
    for field, value in plan.params.model_dump().items():
        lines.append(f"  {field:20s} = {value}")
    lines += [
        "",
        "### Probe Points",
    ]
    for i, pt in enumerate(plan.probe_points):
        lines.append(f"  [{i}] x={pt[0]:.4f}  y={pt[1]:.4f}  z={pt[2]:.4f}")
    lines += [
        "",
        "=" * 64,
        "A visualization of the particle configuration has been generated.",
        "Approve, request changes, or ask a question:",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Responses API history helpers
# ─────────────────────────────────────────────────────────────────────────────


def _user_message(text: str) -> dict:
    """Build a Responses API user message item."""
    return {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": text}],
    }


def _user_message_with_image(text: str, image_b64: str, media_type: str) -> dict:
    """Build a Responses API user message with text + image."""
    return {
        "type": "message",
        "role": "user",
        "content": [
            {"type": "input_text", "text": text},
            {
                "type": "input_image",
                "image_url": f"data:{media_type};base64,{image_b64}",
            },
        ],
    }


def _assistant_message(text: str) -> dict:
    """Build a Responses API assistant message item."""
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text}],
    }


def _function_call_item(fc) -> dict:
    """Serialize a function_call output item for history."""
    return {
        "type": "function_call",
        "id": fc.id,
        "call_id": fc.call_id,
        "name": fc.name,
        "arguments": fc.arguments,
    }


def _function_call_output(call_id: str, output: str) -> dict:
    """Build a function_call_output item for history."""
    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }


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

    def _inject_datalake_xml(self, scenario: str, rel_path: str, abs_path: Path, ctx: WorkflowContext) -> Message:
        """Read datalake XML and inject it into the scenario as a text message."""
        xml_content = abs_path.read_text()
        ctx.set_state("base_xml", str(abs_path))
        logger.info("PlanAndBuildExecutor: injected datalake XML %s", abs_path)
        text = (
            f"{scenario}\n\n"
            f"### Existing Case XML ({rel_path})\n"
            f"```xml\n{xml_content}\n```\n\n"
            "Modify this existing case according to the user's instructions. "
            "You may reuse or adjust the geometry, parameters, and probe points."
        )
        return Message("user", text=text)

    def _inject_datalake_image(self, scenario: str, rel_path: str, abs_path: Path) -> Message:
        """Read a datalake image and create a multimodal message."""
        image_bytes = abs_path.read_bytes()
        suffix = abs_path.suffix.lower()
        media_type = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}[suffix]
        logger.info("PlanAndBuildExecutor: injected datalake image %s", abs_path)
        text = (
            f"{scenario}\n\n"
            f"### Reference Geometry Image ({rel_path})\n"
            "The image above shows the target geometry. Study it carefully and "
            "create DualSPHysics XML geometry that reproduces this configuration. "
            "Pay attention to dimensions, shapes, positions, and boundaries."
        )
        return Message("user", [text, Content.from_data(image_bytes, media_type)])

    @handler
    async def start(self, scenario: str, ctx: WorkflowContext[AgentExecutorRequest | ReviewResult]) -> None:
        """Initial entry: receive a natural-language scenario."""
        logger.info("PlanAndBuildExecutor: new scenario (%d chars)", len(scenario))
        ctx.set_state("scenario", scenario)

        available = _list_datalake_files(self.base_dir)
        matched = await resolve_datalake_file(scenario, available) if available else None

        if matched:
            abs_path = Path(self.base_dir) / matched
            if _is_image_file(abs_path):
                msg = self._inject_datalake_image(scenario, matched, abs_path)
                # Store path so setup review can load the image lazily
                ctx.set_state("datalake_image_path", matched)
            else:
                msg = self._inject_datalake_xml(scenario, matched, abs_path, ctx)
            await ctx.send_message(AgentExecutorRequest(messages=[msg], should_respond=True))
            return

        msg = Message("user", text=scenario)
        await ctx.send_message(AgentExecutorRequest(messages=[msg], should_respond=True))

    @handler
    async def on_revision(self, review: ReviewResult, ctx: WorkflowContext[AgentExecutorRequest | ReviewResult]) -> None:
        """Full replan: the user wants to start over with a different scenario."""
        plan_data = ctx.get_state("plan")
        text = f"Please revise the simulation: {review.feedback}"
        if plan_data:
            text += f"\n\n### Previous Plan\n```json\n{json.dumps(plan_data, indent=2)}\n```"
        logger.info("PlanAndBuildExecutor: revision request — %s", review.feedback)
        msg = Message("user", text=text)
        await ctx.send_message(AgentExecutorRequest(messages=[msg], should_respond=True))

    # ── Build + review init ──────────────────────────────────────────────

    def _new_run_dir(self) -> str:
        """Create a timestamped run directory path for the current build."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"{self.base_dir}/runs/run_{ts}"

    async def _build(self, plan_data: dict, base_xml: str, run_dir: str) -> str:
        """set_geometry -> modify_xml -> generate_points -> run_gencase -> visualize."""
        geometry_xml: str = plan_data["geometry_xml"]
        params = PhysicsParams(**plan_data["params"])
        probe_points: list[list[float]] = plan_data["probe_points"]

        Path(run_dir).mkdir(parents=True, exist_ok=True)
        case_xml = f"{run_dir}/Case_Def.xml"

        # 1. Set geometry
        logger.info(">>> set_geometry")
        r = await self.mcp.call_tool(
            "set_geometry",
            base_xml=base_xml,
            output_xml=case_xml,
            geometry_xml=geometry_xml,
        )
        if r.startswith("ERROR"):
            raise RuntimeError(f"set_geometry failed: {r}")
        logger.info("set_geometry OK")

        # 2. Modify physics parameters
        logger.info(">>> modify_xml")
        r = await self.mcp.call_tool(
            "modify_xml",
            base_xml=case_xml,
            output_xml=case_xml,
            **params.model_dump(),
        )
        logger.info("modify_xml OK: %s", r)

        # 3. Generate probe points file
        logger.info(">>> generate_points_file")
        r = await self.mcp.call_tool(
            "generate_points_file",
            output_path=f"{run_dir}/PointsMeasure_Points.txt",
            probe_points=probe_points,
        )
        logger.info("generate_points_file OK: %s", r)

        # 4. Run GenCase
        logger.info(">>> run_gencase")
        r = await self.mcp.call_tool(
            "run_gencase",
            xml_path=f"{run_dir}/Case_Def",  # no .xml extension
            output_dir=f"{run_dir}/out",
        )
        result = json.loads(r) if isinstance(r, str) else r
        if result.get("returncode", -1) != 0:
            raise RuntimeError(f"run_gencase failed: {result.get('stderr', r)}")
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

        # Run build pipeline
        build_error: str | None = None
        try:
            await self._build(plan_data, base_xml, run_dir)
        except Exception as exc:
            logger.exception("Build pipeline failed")
            build_error = str(exc)

        # Build plan summary
        summary = _format_plan_summary(plan)
        if build_error:
            logger.warning("Build failed: %s — entering setup review recovery loop", build_error)
            summary = (
                f"{summary}\n\n"
                "Build failed before the setup could be reviewed.\n"
                f"Error:\n{build_error}\n\n"
                "You can request a fix, manually edit the XML, ask a question, or replan."
            )

        # Initialize review state
        if build_error:
            self._set_recovery_state(ctx, build_error, retry_count=0)
        else:
            self._set_recovery_state(ctx)
        self._refresh_instructions(ctx, plan_data, run_dir)

        # Initialize conversation history (Responses API format — no system message)
        history: list[dict] = []

        # Inject datalake reference image into setup review history so the
        # review LLM can see it when the user asks about "the image".
        datalake_image_rel = ctx.get_state("datalake_image_path")
        if datalake_image_rel:
            abs_path = Path(self.base_dir) / datalake_image_rel
            if abs_path.exists():
                suffix = abs_path.suffix.lower()
                media_type = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}[suffix]
                img_b64 = base64.b64encode(abs_path.read_bytes()).decode()
                history.append(_user_message_with_image(
                    f"Here is the reference image from the datalake ({datalake_image_rel}). "
                    "Use it to verify the geometry setup matches the target.",
                    img_b64,
                    media_type,
                ))
                history.append(_assistant_message(
                    "I can see the reference image. I'll use it to help review "
                    "whether the simulation geometry matches the target."
                ))

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
        """Rebuild and store the review LLM instructions (used as Responses API `instructions`)."""
        instructions = _build_instructions(
            plan_data,
            run_dir,
            build_error=ctx.get_state("setup_review_last_error"),
            retry_count=ctx.get_state("setup_review_retry_count") or 0,
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
        """Process user reply through the LLM tool-use loop (Responses API)."""
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
            history.append(_user_message(feedback or "no"))
            log_message(run_dir, "user", feedback or "no", phase="setup_review")

        # Check if we're resuming after a manual edit pause
        pending_manual_edit = ctx.get_state("pending_manual_edit")
        if pending_manual_edit:
            ctx.set_state("pending_manual_edit", False)
            try:
                await rebuild_gencase_viz(self.mcp, run_dir)
                self._set_recovery_state(ctx)
                instructions = self._refresh_instructions(ctx, plan_data, run_dir)
                history.append(_function_call_output(
                    pending_manual_edit,
                    "Manual edit complete. GenCase rebuilt and visualization regenerated.",
                ))
            except Exception as exc:
                logger.exception("Manual edit rebuild failed")
                retry_count = self._record_recovery_failure(ctx, str(exc))
                instructions = self._refresh_instructions(ctx, plan_data, run_dir)
                history.append(_function_call_output(
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
            history.append(_user_message(feedback or "approve"))
            log_message(run_dir, "user", feedback or "approve", phase="setup_review")

        client = AsyncOpenAI()

        while True:
            response = await client.responses.create(
                model=os.getenv("INTENT_MODEL", "gpt-4o-mini"),
                temperature=0,
                input=history,
                instructions=instructions,
                tools=_TOOLS,
            )

            # Separate output into text and function calls
            function_calls = []
            assistant_text = ""

            for item in response.output:
                if item.type == "message":
                    for content_block in item.content:
                        if content_block.type == "output_text":
                            assistant_text += content_block.text
                    history.append(_assistant_message(assistant_text))
                elif item.type == "function_call":
                    function_calls.append(item)
                    history.append(_function_call_item(item))

            if not function_calls:
                # Pure text response — send to user
                ctx.set_state("setup_review_history", history)
                log_message(run_dir, "assistant", assistant_text, phase="setup_review")
                await ctx.request_info(
                    request_data=SetupReviewRequest(summary=assistant_text),
                    response_type=str,
                )
                return

            for fc in function_calls:
                fn_name = fc.name
                fn_args = json.loads(fc.arguments)

                if fn_name == "approve":
                    last_error = ctx.get_state("setup_review_last_error")
                    if last_error:
                        history.append(_function_call_output(
                            fc.call_id,
                            "Cannot approve yet because the current setup still has an "
                            f"unresolved build error: {last_error}. "
                            "Fix it first with `patch_and_rebuild`, `manual_edit`, or `replan`.",
                        ))
                        continue
                    history.append(_function_call_output(
                        fc.call_id,
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
                        history.append(_function_call_output(fc.call_id, result_text))
                    except Exception as exc:
                        logger.exception("patch_and_rebuild failed")
                        retry_count = self._record_recovery_failure(ctx, str(exc))
                        instructions = self._refresh_instructions(ctx, plan_data, run_dir)
                        history.append(_function_call_output(fc.call_id, f"Error: {exc}"))
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
                    ctx.set_state("pending_manual_edit", fc.call_id)
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
                    history.append(_function_call_output(fc.call_id, ref_content))

                elif fn_name == "answer_question":
                    question = fn_args["question"]
                    plan_context = json.dumps(plan_data, indent=2)
                    answer = await answer_question(question, plan_context)
                    history.append(_function_call_output(fc.call_id, answer))

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
            if r.startswith("ERROR"):
                raise RuntimeError(f"set_geometry failed: {r}")

        if "params" in patch:
            logger.info(">>> modify_xml (patch)")
            merged_params = {**plan_data["params"], **patch["params"]}
            await self.mcp.call_tool(
                "modify_xml",
                base_xml=case_xml,
                output_xml=case_xml,
                **merged_params,
            )

        if "probe_points" in patch:
            logger.info(">>> generate_points_file (patch)")
            await self.mcp.call_tool(
                "generate_points_file",
                output_path=f"{run_dir}/PointsMeasure_Points.txt",
                probe_points=patch["probe_points"],
            )

        merge_patch(plan_data, patch)
        ctx.set_state("plan", plan_data)

        await rebuild_gencase_viz(self.mcp, run_dir)

        return "Patch applied successfully. Visualization regenerated with the updated geometry."
