"""ManualEditExecutor — HITL manual XML editing.

Pauses the workflow so the user can edit Case_Def.xml directly,
then re-runs gencase + visualization on resume.
"""

import logging

from agent_framework import (
    Executor,
    MCPStdioTool,
    WorkflowContext,
    handler,
    response_handler,
)

from agents.utils.build_utils import rebuild_gencase_viz
from agents.schemas import BuildResult, ManualEditAck, ManualEditRequest

logger = logging.getLogger(__name__)


class ManualEditExecutor(Executor):
    """Pauses for user to manually edit XML, then rebuilds."""

    def __init__(self, mcp: MCPStdioTool) -> None:
        super().__init__(id="manual_edit")
        self.mcp = mcp

    @handler
    async def on_manual_edit(
        self,
        req: ManualEditRequest,
        ctx: WorkflowContext[BuildResult],
    ) -> None:
        """Print the file path and pause for user edits."""
        run_dir = ctx.get_state("run_dir")
        if run_dir is None:
            await ctx.send_message(BuildResult(
                run_dir="",
                success=False,
                message="No run_dir — build the case first before editing manually.",
            ))
            return

        file_path = f"{run_dir}/Case_Def.xml"
        await ctx.request_info(
            request_data=ManualEditAck(
                file_path=file_path,
                message=(
                    f"Edit the case file at:\n  {file_path}\n\n"
                    "Type 'done' when finished editing."
                ),
            ),
            response_type=str,
        )

    @response_handler
    async def on_done(
        self,
        request: ManualEditAck,
        response: str,
        ctx: WorkflowContext[BuildResult],
    ) -> None:
        """User finished editing — rebuild gencase + viz."""
        run_dir = ctx.get_state("run_dir")
        assert run_dir is not None

        try:
            await rebuild_gencase_viz(self.mcp, run_dir)
            await ctx.send_message(BuildResult(
                run_dir=run_dir,
                success=True,
                message="Manual edit rebuild complete",
            ))
        except Exception as exc:
            logger.exception("Manual edit rebuild failed")
            await ctx.send_message(BuildResult(
                run_dir=run_dir,
                success=False,
                message=str(exc),
            ))
