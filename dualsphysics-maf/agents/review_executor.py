"""ReviewExecutor — HITL gates with LLM intent classification.

Handles two review phases:
  1. Plan review (after agent produces SimulationPlan)
  2. Viz review (after BuildExecutor/PatchExecutor/ManualEditExecutor)

Uses 5-way classify_intent() to route user feedback.
"""

import logging

from agent_framework import (
    AgentExecutorResponse,
    Executor,
    WorkflowContext,
    handler,
    response_handler,
)

from agents.intent import answer_question, classify_intent
from agents.schemas import (
    BuildResult,
    ManualEditRequest,
    PatchRequest,
    ReviewRequest,
    ReviewResult,
    SimulationPlan,
)

logger = logging.getLogger(__name__)


def _format_plan_summary(plan: SimulationPlan) -> str:
    """Build a human-readable summary of the simulation plan."""
    lines = [
        "=" * 64,
        "  SIMULATION PLAN — REVIEW REQUIRED",
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
        "Approve, request changes, or ask a question:",
    ]
    return "\n".join(lines)


class ReviewExecutor(Executor):
    """HITL review gates for plan and visualization phases."""

    def __init__(self) -> None:
        super().__init__(id="review")

    @handler
    async def on_plan(self, result: AgentExecutorResponse, ctx: WorkflowContext[ReviewResult | PatchRequest | ManualEditRequest]) -> None:
        """Receive the agent's SimulationPlan and request user review."""
        raw_text = result.agent_response.text
        logger.info("ReviewExecutor: agent response length: %d chars", len(raw_text))

        plan = SimulationPlan.model_validate_json(raw_text)
        ctx.set_state("plan", plan.model_dump())

        summary = _format_plan_summary(plan)
        await ctx.request_info(
            request_data=ReviewRequest(phase="plan", summary=summary),
            response_type=str,
        )

    @handler
    async def on_build_complete(self, result: BuildResult, ctx: WorkflowContext[ReviewResult | PatchRequest | ManualEditRequest]) -> None:
        """After build pipeline: show viz prompt or auto-route to revision on failure."""
        if not result.success:
            logger.warning("Build failed: %s — auto-routing to full replan", result.message)
            await ctx.send_message(
                ReviewResult(route="full_replan", feedback=f"Build failed: {result.message}", phase="plan")
            )
            return

        await ctx.request_info(
            request_data=ReviewRequest(
                phase="viz",
                summary=(
                    "ParaView should be open with the particle configuration.\n"
                    "Does the geometry look correct?\n"
                    "Approve, request changes, or ask a question:"
                ),
            ),
            response_type=str,
        )

    @response_handler
    async def on_feedback(
        self,
        request: ReviewRequest,
        feedback: str,
        ctx: WorkflowContext[ReviewResult | PatchRequest | ManualEditRequest],
    ) -> None:
        """5-way classification of user feedback."""
        intent = await classify_intent(feedback)
        logger.info("ReviewExecutor: phase=%s, intent=%s", request.phase, intent)

        if intent == "question":
            plan_data = ctx.get_state("plan")
            if plan_data:
                plan = SimulationPlan.model_validate(plan_data)
                plan_context = _format_plan_summary(plan)
            else:
                plan_context = request.summary

            answer = await answer_question(feedback, plan_context, skill_type="xml")

            await ctx.request_info(
                request_data=ReviewRequest(
                    phase=request.phase,
                    summary=f"{answer}\n\n{'=' * 64}\nApprove, request changes, or ask a question:",
                ),
                response_type=str,
            )
            return

        if intent == "approve":
            route = "build" if request.phase == "plan" else "sim"
            await ctx.send_message(
                ReviewResult(route=route, feedback=feedback, phase=request.phase)
            )
        elif intent == "agent_patch":
            await ctx.send_message(
                PatchRequest(feedback=feedback, phase=request.phase)
            )
        elif intent == "manual_edit":
            await ctx.send_message(
                ManualEditRequest(phase=request.phase)
            )
        else:  # full_replan
            await ctx.send_message(
                ReviewResult(route="full_replan", feedback=feedback, phase=request.phase)
            )
