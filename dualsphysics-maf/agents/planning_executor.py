"""PlanningExecutor — entry point that wraps a scenario or revision
feedback into an AgentExecutorRequest for the LLM reasoning agent."""

import logging

from agent_framework import (
    AgentExecutorRequest,
    Executor,
    Message,
    WorkflowContext,
    handler,
)

from agents.schemas import ReviewResult

logger = logging.getLogger(__name__)


class PlanningExecutor(Executor):
    """Wraps scenario text or revision feedback into an AgentExecutorRequest."""

    def __init__(self) -> None:
        super().__init__(id="planning")

    @handler
    async def start(self, scenario: str, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        """Initial entry: receive a natural-language scenario."""
        logger.info("PlanningExecutor: new scenario (%d chars)", len(scenario))
        msg = Message("user", text=scenario)
        await ctx.send_message(AgentExecutorRequest(messages=[msg], should_respond=True))

    @handler
    async def on_revision(self, review: ReviewResult, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        """Revision loop: the user requested changes to the plan or geometry."""
        if review.phase == "plan":
            text = f"Please revise the plan: {review.feedback}"
        else:
            text = f"Revise the geometry based on visual inspection: {review.feedback}"
        logger.info("PlanningExecutor: revision request — %s", text)
        msg = Message("user", text=text)
        await ctx.send_message(AgentExecutorRequest(messages=[msg], should_respond=True))
