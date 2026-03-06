"""SimExecutor — deterministic simulation pipeline.

Reads plan + run_dir from workflow state and runs:
  run_simulation → run_measuretool → compute_metrics → yield_output
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
    """Deterministic: runs the full simulation and collects metrics."""

    def __init__(self, mcp: MCPStdioTool, base_dir: str) -> None:
        super().__init__(id="sim")
        self.mcp = mcp
        self.base_dir = base_dir

    @handler
    async def on_approved(self, trigger: ReviewResult, ctx: WorkflowContext[dict]) -> None:
        """Run the 3-step simulation pipeline and yield final output."""
        plan_data = ctx.get_state("plan")
        run_dir = ctx.get_state("run_dir")
        assert plan_data is not None, "No plan in workflow state"
        assert run_dir is not None, "No run_dir in workflow state"

        # 1. Run simulation (GPU if available, else CPU)
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
            raise RuntimeError(f"run_simulation failed: {sim_result.get('stderr', r)}")
        logger.info("run_simulation OK")

        # 2. Run MeasureTool
        logger.info(">>> run_measuretool")
        r = await self.mcp.call_tool(
            "run_measuretool",
            data_dir=f"{run_dir}/out/data",
            points_file=f"{run_dir}/PointsMeasure_Points.txt",
            output_csv_stem=f"{run_dir}/out/measuretool/PointsMeasure",
        )
        mt_result = json.loads(r) if isinstance(r, str) else r
        if mt_result.get("returncode", -1) != 0:
            raise RuntimeError(f"run_measuretool failed: {mt_result.get('stderr', r)}")
        csv_files = mt_result.get("csv_files", [])
        if not csv_files:
            raise RuntimeError("run_measuretool produced no CSV files")
        logger.info("run_measuretool OK: %s", csv_files)

        # 3. Compute metrics
        logger.info(">>> compute_metrics")
        r = await self.mcp.call_tool(
            "compute_metrics",
            result_csv=csv_files[0],
            ground_truth_csv=f"{self.base_dir}/cases/ground_truth/PointsMeasure.csv",
        )
        metrics = json.loads(r) if isinstance(r, str) else r
        logger.info("compute_metrics: %s", metrics)

        await ctx.yield_output({
            "geometry_xml": plan_data["geometry_xml"],
            "params": plan_data["params"],
            "probe_points": plan_data["probe_points"],
            "rmse": metrics.get("rmse"),
            "correlation": metrics.get("correlation"),
            "run_dir": run_dir,
            "status": "ok",
        })
