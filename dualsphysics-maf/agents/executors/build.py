"""BuildExecutor — deterministic build pipeline.

Triggered automatically after the agent produces a SimulationPlan.
Runs: set_geometry -> modify_xml -> generate_points -> run_gencase -> visualize
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from agent_framework import (
    AgentExecutorResponse,
    Executor,
    MCPStdioTool,
    WorkflowContext,
    handler,
)

from agents.schemas import BuildResult, SimulationPlan
from agents.tools.visualize_geometry import visualize_geometry

logger = logging.getLogger(__name__)


class BuildExecutor(Executor):
    """Deterministic: builds the simulation case from the agent's plan."""

    def __init__(self, mcp: MCPStdioTool, base_dir: str) -> None:
        super().__init__(id="build")
        self.mcp = mcp
        self.base_dir = base_dir

    @handler
    async def on_plan(self, result: AgentExecutorResponse, ctx: WorkflowContext[BuildResult]) -> None:
        """Parse the agent's SimulationPlan and run the 5-step build pipeline."""
        raw_text = result.agent_response.text
        logger.info("BuildExecutor: agent response length: %d chars", len(raw_text))

        plan = SimulationPlan.model_validate_json(raw_text)
        ctx.set_state("plan", plan.model_dump())

        base_xml = ctx.get_state("base_xml") or f"{self.base_dir}/cases/BaseCase_Def.xml"
        run_dir = self._new_run_dir()
        ctx.set_state("run_dir", run_dir)

        try:
            await self._build(plan.model_dump(), base_xml, run_dir)
            await ctx.send_message(BuildResult(run_dir=run_dir, success=True, message="Build complete"))
        except Exception as exc:
            logger.exception("Build pipeline failed")
            await ctx.send_message(BuildResult(run_dir=run_dir, success=False, message=str(exc)))

    def _new_run_dir(self) -> str:
        """Create a timestamped run directory path for the current build."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"{self.base_dir}/runs/run_{ts}"

    async def _build(self, plan_data: dict, base_xml: str, run_dir: str) -> str:
        """set_geometry -> modify_xml -> generate_points -> run_gencase -> visualize."""
        from agents.schemas import PhysicsParams

        geometry_xml: str = plan_data["geometry_xml"]
        params = PhysicsParams(**plan_data["params"])
        probe_points: list[list[float]] = plan_data["probe_points"]

        Path(run_dir).mkdir(parents=True, exist_ok=True)
        case_xml = f"{run_dir}/Case_Def.xml"

        # 1. Set geometry
        logger.info(">>> set_geometry")
        r = await self.mcp.call_tool(
            "set_geometry",
            base_xml=base_xml,
            output_xml=case_xml,
            geometry_xml=geometry_xml,
        )
        if r.startswith("ERROR"):
            raise RuntimeError(f"set_geometry failed: {r}")
        logger.info("set_geometry OK")

        # 2. Modify physics parameters
        logger.info(">>> modify_xml")
        r = await self.mcp.call_tool(
            "modify_xml",
            base_xml=case_xml,
            output_xml=case_xml,
            **params.model_dump(),
        )
        logger.info("modify_xml OK: %s", r)

        # 3. Generate probe points file
        logger.info(">>> generate_points_file")
        r = await self.mcp.call_tool(
            "generate_points_file",
            output_path=f"{run_dir}/PointsMeasure_Points.txt",
            probe_points=probe_points,
        )
        logger.info("generate_points_file OK: %s", r)

        # 4. Run GenCase
        logger.info(">>> run_gencase")
        r = await self.mcp.call_tool(
            "run_gencase",
            xml_path=f"{run_dir}/Case_Def",  # no .xml extension
            output_dir=f"{run_dir}/out",
        )
        result = json.loads(r) if isinstance(r, str) else r
        if result.get("returncode", -1) != 0:
            raise RuntimeError(f"run_gencase failed: {result.get('stderr', r)}")
        logger.info("run_gencase OK")

        # 5. Visualize (direct Python call, not MCP)
        logger.info(">>> visualize_geometry")
        viz_result = visualize_geometry(f"{run_dir}/out")
        logger.info("visualize_geometry: %s", viz_result)

        return run_dir
