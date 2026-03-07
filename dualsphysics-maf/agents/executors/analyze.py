"""AnalyzeExecutor — default post-processing of simulation results.

Runs standard post-processing automatically after simulation:
- PartVTK: export fluid and boundary particles as VTK for ParaView
- MeasureTool: extract probe data
- compute_metrics: compare with ground truth (if available)
- Opens ParaView with the results
"""

import json
import logging
import os

from agent_framework import (
    Executor,
    MCPStdioTool,
    WorkflowContext,
    handler,
)

from agents.schemas import AnalysisResult, ReviewResult
from agents.tools.visualize_geometry import visualize_geometry

logger = logging.getLogger(__name__)


class AnalyzeExecutor(Executor):
    """Default post-processing of simulation results."""

    def __init__(self, mcp: MCPStdioTool, base_dir: str) -> None:
        super().__init__(id="analyze")
        self.mcp = mcp
        self.base_dir = base_dir

    @handler
    async def on_sim_complete(
        self, trigger: ReviewResult, ctx: WorkflowContext[AnalysisResult]
    ) -> None:
        """Default post-processing after simulation completes."""
        run_dir = ctx.get_state("run_dir")
        assert run_dir is not None, "No run_dir in workflow state"

        particles_dir = f"{run_dir}/out/particles"

        try:
            # 1. PartVTK: export fluid particles as VTK
            logger.info(">>> partvtk (fluid VTK)")
            r = await self.mcp.call_tool(
                "run_postprocess",
                postprocess_tool="partvtk",
                cwd=run_dir,
                args=[
                    "-dirin", "out/data",
                    "-savevtk", "out/particles/PartFluid",
                    "-onlytype:-all,+fluid",
                    "-vars:+idp,+vel,+rhop,+press",
                ],
            )
            partvtk_result = json.loads(r) if isinstance(r, str) else r
            if partvtk_result.get("returncode", -1) != 0:
                logger.warning("PartVTK failed: %s", partvtk_result.get("stderr"))

            # 2. PartVTK: export boundary particles as VTK
            logger.info(">>> partvtk (boundary VTK)")
            r = await self.mcp.call_tool(
                "run_postprocess",
                postprocess_tool="partvtk",
                cwd=run_dir,
                args=[
                    "-dirin", "out/data",
                    "-savevtk", "out/particles/PartBound",
                    "-onlytype:-all,+bound",
                    "-vars:+mk,+rhop",
                ],
            )

            # 3. MeasureTool: probe data (if points file exists)
            points_file = f"{run_dir}/PointsMeasure_Points.txt"
            csv_files = []
            if os.path.exists(points_file):
                logger.info(">>> run_measuretool")
                r = await self.mcp.call_tool(
                    "run_measuretool",
                    data_dir=f"{run_dir}/out/data",
                    points_file=points_file,
                    output_csv_stem=f"{run_dir}/out/measuretool/PointsMeasure",
                )
                mt_result = json.loads(r) if isinstance(r, str) else r
                csv_files = mt_result.get("csv_files", [])

            # 4. Compute metrics (if ground truth exists)
            gt_csv = f"{self.base_dir}/cases/ground_truth/PointsMeasure.csv"
            metrics = {}
            if csv_files and os.path.exists(gt_csv):
                logger.info(">>> compute_metrics")
                r = await self.mcp.call_tool(
                    "compute_metrics",
                    result_csv=csv_files[0],
                    ground_truth_csv=gt_csv,
                )
                metrics = json.loads(r) if isinstance(r, str) else r

            # 5. Open ParaView with fluid VTK
            logger.info(">>> visualize results")
            viz_result = visualize_geometry(particles_dir)
            logger.info("visualize: %s", viz_result)

            # Collect all output files
            output_files = partvtk_result.get("output_files", []) + csv_files

            summary_parts = [
                "Default post-processing complete:",
                f"  - Fluid VTK files: out/particles/PartFluid_*.vtk",
                f"  - Boundary VTK files: out/particles/PartBound_*.vtk",
            ]
            if csv_files:
                rel_csvs = [os.path.relpath(f, run_dir) for f in csv_files]
                summary_parts.append(f"  - Probe CSVs: {', '.join(rel_csvs)}")
            if metrics.get("rmse") is not None:
                summary_parts.append(
                    f"  - Metrics: RMSE={metrics['rmse']:.6f}, "
                    f"correlation={metrics.get('correlation', 'N/A')}"
                )

            await ctx.send_message(AnalysisResult(
                run_dir=run_dir,
                success=True,
                message="\n".join(summary_parts),
                output_files=output_files,
            ))

        except Exception as exc:
            logger.exception("Default post-processing failed")
            await ctx.send_message(AnalysisResult(
                run_dir=run_dir,
                success=False,
                message=str(exc),
                output_files=[],
            ))
