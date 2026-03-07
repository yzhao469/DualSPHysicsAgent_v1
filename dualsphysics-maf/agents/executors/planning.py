"""PlanningExecutor — entry point that wraps a scenario or revision
feedback into an AgentExecutorRequest for the LLM reasoning agent."""

import logging
from pathlib import Path

from agent_framework import (
    AgentExecutorRequest,
    Executor,
    Message,
    WorkflowContext,
    handler,
    response_handler,
)

from agents.utils.intent import resolve_datalake_file
from agents.schemas import ReviewResult

logger = logging.getLogger(__name__)


def _list_datalake_files(base_dir: str) -> list[str]:
    """Return relative paths of all XML files in the datalake directory."""
    datalake = Path(base_dir) / "datalake"
    if not datalake.is_dir():
        return []
    return sorted(
        str(p.relative_to(base_dir)) for p in datalake.glob("**/*.xml")
    )


class PlanningExecutor(Executor):
    """Wraps scenario text or revision feedback into an AgentExecutorRequest."""

    def __init__(self, base_dir: str) -> None:
        super().__init__(id="planning")
        self.base_dir = base_dir

    def _inject_datalake(self, scenario: str, rel_path: str, abs_path: Path, ctx: WorkflowContext) -> str:
        """Read datalake XML and inject it into the scenario text."""
        xml_content = abs_path.read_text()
        ctx.set_state("base_xml", str(abs_path))
        logger.info("PlanningExecutor: injected datalake file %s", abs_path)
        return (
            f"{scenario}\n\n"
            f"### Existing Case XML ({rel_path})\n"
            f"```xml\n{xml_content}\n```\n\n"
            "Modify this existing case according to the user's instructions. "
            "You may reuse or adjust the geometry, parameters, and probe points."
        )

    @handler
    async def start(self, scenario: str, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        """Initial entry: receive a natural-language scenario.

        Uses LLM to detect if the user references a datalake file.
        If matched, injects the XML as context for the agent.
        If the LLM thinks the user references a file but we can't resolve it,
        asks the user to clarify.
        """
        logger.info("PlanningExecutor: new scenario (%d chars)", len(scenario))

        available = _list_datalake_files(self.base_dir)
        matched = await resolve_datalake_file(scenario, available) if available else None

        if matched:
            abs_path = Path(self.base_dir) / matched
            text = self._inject_datalake(scenario, matched, abs_path, ctx)
            msg = Message("user", text=text)
            await ctx.send_message(AgentExecutorRequest(messages=[msg], should_respond=True))
            return

        # No datalake file matched — proceed without base case
        msg = Message("user", text=scenario)
        await ctx.send_message(AgentExecutorRequest(messages=[msg], should_respond=True))

    @handler
    async def on_revision(self, review: ReviewResult, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        """Full replan: the user wants to start over with a different scenario."""
        text = f"Please revise the simulation: {review.feedback}"
        logger.info("PlanningExecutor: revision request — %s", text)
        msg = Message("user", text=text)
        await ctx.send_message(AgentExecutorRequest(messages=[msg], should_respond=True))
