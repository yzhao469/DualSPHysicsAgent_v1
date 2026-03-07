"""ReviewExecutor — HITL gates with LLM intent classification.

Handles three review phases:
  1. Plan review (after agent produces SimulationPlan)
  2. Viz review (after BuildExecutor/PatchExecutor/ManualEditExecutor)
  3. Results review (after AnalyzeExecutor post-processing)

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

from agents.utils.intent import answer_question, classify_intent
from agents.schemas import (
    AnalysisRequest,
    AnalysisResult,
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
    """HITL review gates for plan, visualization, and results phases."""

    def __init__(self) -> None:
        super().__init__(id="review")

    @handler
    async def on_plan(self, result: AgentExecutorResponse, ctx: WorkflowContext[ReviewResult | PatchRequest | ManualEditRequest | AnalysisRequest]) -> None:
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
    async def on_build_complete(self, result: BuildResult, ctx: WorkflowContext[ReviewResult | PatchRequest | ManualEditRequest | AnalysisRequest]) -> None:
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

    @handler
    async def on_analysis_complete(self, result: AnalysisResult, ctx: WorkflowContext[ReviewResult | PatchRequest | ManualEditRequest | AnalysisRequest]) -> None:
        """After post-processing: show results and ask for further analysis."""
        if not result.success:
            logger.warning("Analysis failed: %s", result.message)

        summary_parts = [
            "=" * 64,
            "  SIMULATION RESULTS",
            "=" * 64,
            "",
            result.message,
            "",
        ]
        if result.output_files:
            summary_parts.append("Generated files:")
            for f in result.output_files[:20]:  # limit display
                summary_parts.append(f"  - {f}")
            if len(result.output_files) > 20:
                summary_parts.append(f"  ... and {len(result.output_files) - 20} more")
        summary_parts += [
            "",
            "=" * 64,
            "Request further analysis, or type 'done' to finish:",
        ]

        await ctx.request_info(
            request_data=ReviewRequest(
                phase="results",
                summary="\n".join(summary_parts),
            ),
            response_type=str,
        )

    @response_handler
    async def on_feedback(
        self,
        request: ReviewRequest,
        feedback: str,
        ctx: WorkflowContext[ReviewResult | PatchRequest | ManualEditRequest | AnalysisRequest],
    ) -> None:
        """5-way classification of user feedback."""
        intent = await classify_intent(feedback, phase=request.phase)
        logger.info("ReviewExecutor: phase=%s, intent=%s", request.phase, intent)

        if intent == "question":
            # Build context: always include the current summary (which has
            # results info in the results phase), plus the plan if available.
            context_parts = []
            plan_data = ctx.get_state("plan")
            if plan_data:
                plan = SimulationPlan.model_validate(plan_data)
                context_parts.append(_format_plan_summary(plan))
            if request.phase == "results":
                context_parts.append(f"\n### Current Results Summary\n{request.summary}")
            elif not context_parts:
                context_parts.append(request.summary)

            answer = await answer_question(feedback, "\n".join(context_parts))

            await ctx.request_info(
                request_data=ReviewRequest(
                    phase=request.phase,
                    summary=f"{answer}\n\n{'=' * 64}\nApprove, request changes, or ask a question:",
                ),
                response_type=str,
            )
            return

        if intent == "approve":
            if request.phase == "confirm_replan":
                # User confirmed the full replan warning
                await ctx.send_message(
                    ReviewResult(route="full_replan", feedback=feedback, phase="results")
                )
            elif request.phase == "plan":
                await ctx.send_message(
                    ReviewResult(route="build", feedback=feedback, phase=request.phase)
                )
            elif request.phase == "viz":
                await ctx.send_message(
                    ReviewResult(route="sim", feedback=feedback, phase=request.phase)
                )
            else:  # results — terminal: yield final output
                plan_data = ctx.get_state("plan") or {}
                run_dir = ctx.get_state("run_dir") or ""
                await ctx.yield_output({
                    "status": "complete",
                    "run_dir": run_dir,
                    "params": plan_data.get("params"),
                    "probe_points": plan_data.get("probe_points"),
                })

        elif intent == "agent_patch":
            if request.phase == "results":
                # In results phase, "agent_patch" means "do more analysis"
                await ctx.send_message(
                    AnalysisRequest(feedback=feedback)
                )
            else:
                await ctx.send_message(
                    PatchRequest(feedback=feedback, phase=request.phase)
                )

        elif intent == "manual_edit":
            if request.phase == "results":
                # Manual edit doesn't apply to results — treat as analysis request
                await ctx.send_message(
                    AnalysisRequest(feedback=feedback)
                )
            else:
                await ctx.send_message(
                    ManualEditRequest(phase=request.phase)
                )

        else:  # full_replan
            if request.phase == "results":
                # Warn user and use special phase to track confirmation
                await ctx.request_info(
                    request_data=ReviewRequest(
                        phase="confirm_replan",
                        summary=(
                            "WARNING: Re-planning will discard current simulation "
                            "results and require a full re-run (which may take a long "
                            "time). Type 'yes' to confirm, or describe what analysis "
                            "you'd like instead:"
                        ),
                    ),
                    response_type=str,
                )
            elif request.phase == "confirm_replan":
                # User confirmed full replan from results
                await ctx.send_message(
                    ReviewResult(route="full_replan", feedback=feedback, phase="results")
                )
            else:
                await ctx.send_message(
                    ReviewResult(route="full_replan", feedback=feedback, phase=request.phase)
                )
