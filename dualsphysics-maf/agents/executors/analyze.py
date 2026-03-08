"""AnalyzeExecutor — default post-processing of simulation results.

Generates a postprocess.sh script from the simulation plan, then parses
and executes each command individually via MCP for structured feedback.
The script is a real standalone .sh that users can run independently.
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
from agents.utils.script_utils import generate_script, parse_script

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
        """Generate postprocess.sh, parse it, and run each command via MCP."""
        run_dir = ctx.get_state("run_dir")
        assert run_dir is not None, "No run_dir in workflow state"

        plan_data = ctx.get_state("plan") or {}
        bin_dir = os.path.join(self.base_dir, "bin", "linux")

        # 1. Generate the script
        script_text = generate_script(plan_data, run_dir, bin_dir)
        script_path = os.path.join(run_dir, "postprocess.sh")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_text)
        os.chmod(script_path, 0o755)
        logger.info("Generated %s", script_path)

        # 2. Parse and execute each command
        commands = parse_script(script_text)
        all_output_files: list[str] = []
        failed_steps: list[str] = []

        for cmd in commands:
            logger.info(">>> %s %s", cmd.tool_name, " ".join(cmd.args))
            try:
                if cmd.tool_name == "measuretool":
                    # MeasureTool has its own MCP tool with richer output
                    r = await self.mcp.call_tool(
                        "run_measuretool",
                        data_dir=f"{run_dir}/out/data",
                        points_file=f"{run_dir}/PointsMeasure_Points.txt",
                        output_csv_stem=f"{run_dir}/out/measuretool/PointsMeasure",
                    )
                    result = json.loads(r) if isinstance(r, str) else r
                    all_output_files.extend(result.get("csv_files", []))
                else:
                    r = await self.mcp.call_tool(
                        "run_postprocess",
                        postprocess_tool=cmd.tool_name,
                        cwd=run_dir,
                        args=cmd.args,
                    )
                    result = json.loads(r) if isinstance(r, str) else r
                    if result.get("returncode", -1) != 0:
                        err = result.get("stderr") or result.get("stdout") or "unknown"
                        logger.warning("%s failed: %s", cmd.tool_name, err)
                        failed_steps.append(f"{cmd.tool_name}: {err[:200]}")
                    else:
                        all_output_files.extend(result.get("output_files", []))
            except Exception as exc:
                logger.exception("%s raised an exception", cmd.tool_name)
                failed_steps.append(f"{cmd.tool_name}: {exc}")

        # 3. Compute metrics (if ground truth exists)
        gt_csv = os.path.join(self.base_dir, "cases", "ground_truth", "PointsMeasure.csv")
        csv_files = [f for f in all_output_files if f.endswith(".csv")]
        metrics: dict = {}
        if csv_files and os.path.exists(gt_csv):
            logger.info(">>> compute_metrics")
            r = await self.mcp.call_tool(
                "compute_metrics",
                result_csv=csv_files[0],
                ground_truth_csv=gt_csv,
            )
            metrics = json.loads(r) if isinstance(r, str) else r

        # 4. Visualize results
        particles_dir = f"{run_dir}/out/particles"
        try:
            logger.info(">>> visualize results")
            viz_result = visualize_geometry(particles_dir)
            logger.info("visualize: %s", viz_result)
        except Exception as exc:
            logger.warning("Visualization failed: %s", exc)

        # 5. Build summary
        summary_parts = [
            "Default post-processing complete:",
            f"  - Script: {script_path}",
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
        if failed_steps:
            summary_parts.append(f"  - Failed steps: {'; '.join(failed_steps)}")

        await ctx.send_message(AnalysisResult(
            run_dir=run_dir,
            success=not failed_steps,
            message="\n".join(summary_parts),
            output_files=all_output_files,
            script_path=script_path,
        ))
