"""SimExecutor — deterministic simulation pipeline.

Reads plan + run_dir from workflow state and runs the solver.
No longer terminal — passes control to AnalyzeExecutor for post-processing.
"""

import json
import logging
import shutil

from agent_framework import (
    Executor,
    MCPStdioTool,
    WorkflowContext,
    handler,
)

from agents.schemas import ReviewResult

logger = logging.getLogger(__name__)


def _has_gpu() -> bool:
    """Check whether an NVIDIA GPU is available via nvidia-smi."""
    return shutil.which("nvidia-smi") is not None


class SimExecutor(Executor):
    """Deterministic: runs the DualSPHysics solver."""

    def __init__(self, mcp: MCPStdioTool, base_dir: str) -> None:
        super().__init__(id="sim")
        self.mcp = mcp
        self.base_dir = base_dir

    @handler
    async def on_approved(
        self, trigger: ReviewResult, ctx: WorkflowContext[ReviewResult]
    ) -> None:
        """Run the solver and pass to AnalyzeExecutor."""
        plan_data = ctx.get_state("plan")
        run_dir = ctx.get_state("run_dir")
        assert plan_data is not None, "No plan in workflow state"
        assert run_dir is not None, "No run_dir in workflow state"

        # Run simulation (GPU if available, else CPU)
        use_gpu = _has_gpu()
        logger.info(">>> run_simulation (gpu=%s)", use_gpu)
        r = await self.mcp.call_tool(
            "run_simulation",
            case_path=f"{run_dir}/out/Case_Def",
            output_dir=f"{run_dir}/out",
            gpu=use_gpu,
        )
        sim_result = json.loads(r) if isinstance(r, str) else r
        if sim_result.get("returncode", -1) != 0:
            raise RuntimeError(
                f"run_simulation failed: {sim_result.get('stderr', r)}"
            )
        logger.info("run_simulation OK")

        # Pass to AnalyzeExecutor (default post-processing)
        await ctx.send_message(
            ReviewResult(route="sim", feedback="")
        )
