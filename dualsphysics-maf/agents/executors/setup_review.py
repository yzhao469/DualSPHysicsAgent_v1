"""SetupReviewExecutor — LLM tool-use review loop for plan + viz.

Replaces the old ReviewExecutor (plan+viz phases), PatchExecutor, and
ManualEditExecutor with a single conversational loop backed by OpenAI
function calling.

The user sees the plan summary and ParaView visualization together, then
chats with the LLM to approve, request changes, ask questions, or replan.
"""

import json
import logging
import os
from pathlib import Path

from openai import AsyncOpenAI

from agent_framework import (
    Executor,
    MCPStdioTool,
    WorkflowContext,
    handler,
    response_handler,
)

from agents.schemas import (
    BuildResult,
    PhysicsParams,
    ReviewResult,
    SetupReviewRequest,
    SimulationPlan,
)
from agents.utils.build_utils import rebuild_gencase_viz
from agents.utils.intent import answer_question
from agents.utils.patch_utils import generate_patch, merge_patch
from agents.utils.skill_loader import get_skill_content

logger = logging.getLogger(__name__)
MAX_BUILD_RECOVERY_ATTEMPTS = 3

# OpenAI function definitions for the setup review LLM
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "patch_and_rebuild",
            "description": (
                "Apply changes to the simulation case XML based on the user's "
                "description. Re-runs GenCase and reopens ParaView."
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
    },
    {
        "type": "function",
        "function": {
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
    },
    {
        "type": "function",
        "function": {
            "name": "approve",
            "description": "User is satisfied with the setup. Proceed to simulation.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manual_edit",
            "description": (
                "Let the user manually edit the Case_Def.xml file directly. "
                "Use this when the user says they want to edit the file themselves."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
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
    },
]


def _build_system_prompt(
    plan_data: dict,
    run_dir: str,
    build_error: str | None = None,
    retry_count: int = 0,
    max_retry_count: int = MAX_BUILD_RECOVERY_ATTEMPTS,
) -> str:
    """Build the system prompt for the setup review LLM."""
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
        "The user has been shown the simulation plan and a ParaView visualization "
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
        "ParaView should be open with the particle configuration.",
        "Approve, request changes, or ask a question:",
    ]
    return "\n".join(lines)


class SetupReviewExecutor(Executor):
    """LLM tool-use conversational review of plan + visualization."""

    def __init__(self, mcp: MCPStdioTool, base_dir: str) -> None:
        super().__init__(id="setup_review")
        self.mcp = mcp
        self.base_dir = base_dir

    @staticmethod
    def _reset_recovery_state(ctx: WorkflowContext) -> None:
        """Reset bounded recovery state after a successful build or rebuild."""
        ctx.set_state("setup_review_retry_count", 0)
        ctx.set_state("setup_review_last_error", None)

    @staticmethod
    def _record_recovery_failure(ctx: WorkflowContext, error_message: str) -> int:
        """Track a failed recovery attempt and return the updated count."""
        retry_count = (ctx.get_state("setup_review_retry_count") or 0) + 1
        ctx.set_state("setup_review_retry_count", retry_count)
        ctx.set_state("setup_review_last_error", error_message)
        return retry_count

    @handler
    async def on_build_complete(
        self,
        result: BuildResult,
        ctx: WorkflowContext[ReviewResult],
    ) -> None:
        """After auto-build: show plan + viz, start review loop."""
        plan_data = ctx.get_state("plan")
        plan = SimulationPlan.model_validate(plan_data)
        summary = _format_plan_summary(plan)
        if not result.success:
            logger.warning("Build failed: %s — entering setup review recovery loop", result.message)
            summary = (
                f"{summary}\n\n"
                "Build failed before the setup could be reviewed.\n"
                f"Error:\n{result.message}\n\n"
                "You can request a fix, manually edit the XML, ask a question, or replan."
            )

        # Initialize conversation history
        run_dir = ctx.get_state("run_dir") or result.run_dir
        self._reset_recovery_state(ctx)
        if not result.success:
            ctx.set_state("setup_review_last_error", result.message)
        system_prompt = _build_system_prompt(
            plan_data,
            run_dir,
            build_error=result.message if not result.success else None,
        )
        ctx.set_state("setup_review_history", [
            {"role": "system", "content": system_prompt},
        ])

        await ctx.request_info(
            request_data=SetupReviewRequest(summary=summary),
            response_type=str,
        )

    @response_handler
    async def on_user_reply(
        self,
        request: SetupReviewRequest,
        feedback: str,
        ctx: WorkflowContext[ReviewResult],
    ) -> None:
        """Process user reply through the LLM tool-use loop."""
        history = ctx.get_state("setup_review_history") or []
        plan_data = ctx.get_state("plan")
        run_dir = ctx.get_state("run_dir")

        # Check if we're resuming after a manual edit pause
        pending_manual_edit = ctx.get_state("pending_manual_edit")
        if pending_manual_edit:
            ctx.set_state("pending_manual_edit", False)
            try:
                await rebuild_gencase_viz(self.mcp, run_dir)
                self._reset_recovery_state(ctx)
                history.append({
                    "role": "tool",
                    "tool_call_id": pending_manual_edit,
                    "content": "Manual edit complete. GenCase rebuilt and ParaView reopened.",
                })
            except Exception as exc:
                logger.exception("Manual edit rebuild failed")
                retry_count = self._record_recovery_failure(ctx, str(exc))
                history.append({
                    "role": "tool",
                    "tool_call_id": pending_manual_edit,
                    "content": f"Rebuild failed: {exc}",
                })
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
            # Fall through to the LLM loop so it can respond
        else:
            # Append user message
            history.append({"role": "user", "content": feedback or "approve"})

        client = AsyncOpenAI()

        while True:
            response = await client.chat.completions.create(
                model=os.getenv("INTENT_MODEL", "gpt-4o-mini"),
                temperature=0,
                messages=history,
                tools=_TOOLS,
            )

            choice = response.choices[0]
            msg = choice.message

            # Append assistant message to history
            history.append(msg.model_dump(exclude_none=True))

            if not msg.tool_calls:
                # Text response — show to user and loop
                text = msg.content or ""
                ctx.set_state("setup_review_history", history)
                await ctx.request_info(
                    request_data=SetupReviewRequest(summary=text),
                    response_type=str,
                )
                return

            # Process tool calls
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)

                if fn_name == "approve":
                    ctx.set_state("setup_review_history", history)
                    await ctx.send_message(
                        ReviewResult(route="sim", feedback="approved")
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
                        self._reset_recovery_state(ctx)
                        history.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result_text,
                        })
                    except Exception as exc:
                        logger.exception("patch_and_rebuild failed")
                        retry_count = self._record_recovery_failure(ctx, str(exc))
                        history.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"Error: {exc}",
                        })
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
                    # Pause the loop so the user can edit the file
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

                elif fn_name == "answer_question":
                    question = fn_args["question"]
                    plan_context = json.dumps(plan_data, indent=2)
                    answer = await answer_question(question, plan_context)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": answer,
                    })

            # Continue loop — LLM may chain more tool calls or produce text
            ctx.set_state("setup_review_history", history)

    async def _patch_and_rebuild(
        self,
        changes: str,
        plan_data: dict,
        run_dir: str,
        ctx: WorkflowContext,
    ) -> str:
        """Apply LLM patch, rebuild gencase, reopen ParaView."""
        case_xml = f"{run_dir}/Case_Def.xml"
        if Path(case_xml).exists():
            current_xml = Path(case_xml).read_text()
        else:
            base_xml = ctx.get_state("base_xml") or f"{self.base_dir}/cases/BaseCase_Def.xml"
            current_xml = Path(base_xml).read_text()

        patch = await generate_patch(current_xml, plan_data, changes)
        logger.info("LLM patch keys: %s", list(patch.keys()))

        # Apply geometry patch
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

        # Apply params patch
        if "params" in patch:
            logger.info(">>> modify_xml (patch)")
            merged_params = {**plan_data["params"], **patch["params"]}
            await self.mcp.call_tool(
                "modify_xml",
                base_xml=case_xml,
                output_xml=case_xml,
                **merged_params,
            )

        # Apply probe points patch
        if "probe_points" in patch:
            logger.info(">>> generate_points_file (patch)")
            await self.mcp.call_tool(
                "generate_points_file",
                output_path=f"{run_dir}/PointsMeasure_Points.txt",
                probe_points=patch["probe_points"],
            )

        merge_patch(plan_data, patch)
        ctx.set_state("plan", plan_data)

        # Rebuild gencase + viz
        await rebuild_gencase_viz(self.mcp, run_dir)

        return "Patch applied successfully. ParaView should reopen with the updated geometry."
