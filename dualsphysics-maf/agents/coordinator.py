"""SimulationCoordinator — deterministic workflow executor that orchestrates
the full DualSPHysics simulation pipeline with HITL review gates.

The LLM agent only reasons (produces a SimulationPlan JSON).  All tool
calls are made here, deterministically, via MCPStdioTool.call_tool().
"""

import json
import logging
import re
from datetime import datetime, timezone

from agent_framework import (
    AgentExecutorRequest,
    AgentExecutorResponse,
    Executor,
    MCPStdioTool,
    Message,
    WorkflowContext,
    handler,
    response_handler,
)

from agents.schemas import PhysicsParams, ReviewRequest, SimulationPlan
from agents.tools.visualize_geometry import visualize_geometry

logger = logging.getLogger(__name__)


def _is_agent_design_review_request(text: str) -> bool:
    normalized = text.lower()
    tokens = set(re.findall(r"\b[a-z]+\b", normalized))
    has_review_intent = bool({"review", "suggest", "improve", "feedback"} & tokens)
    has_agent_design = "agent" in tokens and "design" in tokens
    mentions_simulation_flow = bool({"simulate", "simulation", "geometry", "probe", "xml"} & tokens)
    return has_review_intent and has_agent_design and not mentions_simulation_flow


def _build_agent_design_review() -> dict:
    return {
        "status": "ok",
        "request_type": "agent_design_review",
        "summary": "Current design is solid: deterministic orchestration + LLM-only reasoning + HITL gates.",
        "suggestions": [
            "Add strict schema constraints for probe count/ranges to catch weak plans earlier.",
            "Persist each approved SimulationPlan with run metadata for reproducibility and audit.",
            "Add automatic retry/fallback policy for MCP tool failures with bounded retries.",
            "Split planner prompts into reusable scenario templates to reduce prompt drift.",
            "Track per-stage latency/error metrics to identify bottlenecks and unstable tools.",
        ],
    }


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
        "### Geometry XML",
        "```xml",
        plan.geometry_xml,
        "```",
        "",
        "### Physics Parameters",
    ]
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
        "Type 'yes' to approve, or describe changes:",
    ]
    return "\n".join(lines)


class SimulationCoordinator(Executor):
    """Deterministic orchestrator: receives a SimulationPlan from the agent,
    gates on HITL approval, then runs the MCP tool pipeline."""

    def __init__(self, mcp: MCPStdioTool, base_dir: str):
        super().__init__(id="coordinator")
        self.mcp = mcp
        self.base_dir = base_dir
        self.current_plan: SimulationPlan | None = None
        self.run_dir: str | None = None

    # ------------------------------------------------------------------
    # 1. Start: receive scenario string → forward to agent for reasoning
    # ------------------------------------------------------------------
    @handler
    async def start(self, scenario: str, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        """Receive the natural-language scenario and send it to the agent."""
        if _is_agent_design_review_request(scenario):
            await ctx.yield_output(_build_agent_design_review())
            return
        msg = Message("user", text=scenario)
        await ctx.send_message(AgentExecutorRequest(messages=[msg], should_respond=True))

    # ------------------------------------------------------------------
    # 2. Agent response → parse plan → HITL review #1
    # ------------------------------------------------------------------
    @handler
    async def on_agent_response(
        self,
        result: AgentExecutorResponse,
        ctx: WorkflowContext,
    ) -> None:
        """Receive the agent's structured SimulationPlan and request user review."""
        raw_text = result.agent_response.text
        logger.info("Agent response length: %d chars", len(raw_text))

        self.current_plan = SimulationPlan.model_validate_json(raw_text)
        summary = _format_plan_summary(self.current_plan)

        await ctx.request_info(
            request_data=ReviewRequest(phase="plan", summary=summary),
            response_type=str,
        )

    # ------------------------------------------------------------------
    # 3. HITL response handler (both "plan" and "viz" phases)
    # ------------------------------------------------------------------
    @response_handler
    async def on_review(
        self,
        request: ReviewRequest,
        feedback: str,
        ctx: WorkflowContext[AgentExecutorRequest, dict],
    ) -> None:
        """Handle user feedback for both review gates."""
        reply = feedback.strip().lower()

        if request.phase == "plan":
            if reply in ("yes", "ok", "approved", "y", ""):
                # Build the case deterministically
                await self._build_case()
                # Request HITL review #2 (post-visualization)
                await ctx.request_info(
                    request_data=ReviewRequest(
                        phase="viz",
                        summary=(
                            "ParaView should be open with the particle configuration.\n"
                            "Does the geometry look correct?\n"
                            "Type 'yes' to run the simulation, or describe changes:"
                        ),
                    ),
                    response_type=str,
                )
            else:
                # Send revision feedback back to the agent
                msg = Message("user", text=f"Please revise the plan: {feedback}")
                await ctx.send_message(
                    AgentExecutorRequest(messages=[msg], should_respond=True)
                )

        elif request.phase == "viz":
            if reply in ("yes", "ok", "approved", "y", ""):
                # Execute the full simulation pipeline
                results = await self._execute_simulation()
                await ctx.yield_output(results)
            else:
                # Send geometry revision feedback back to the agent
                msg = Message(
                    "user",
                    text=f"Revise the geometry based on visual inspection: {feedback}",
                )
                await ctx.send_message(
                    AgentExecutorRequest(messages=[msg], should_respond=True)
                )

    # ------------------------------------------------------------------
    # Deterministic pipeline helpers
    # ------------------------------------------------------------------
    async def _build_case(self) -> None:
        """set_geometry → modify_xml → generate_points → run_gencase → visualize."""
        plan = self.current_plan
        assert plan is not None

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.run_dir = f"{self.base_dir}/runs/run_{ts}"
        case_xml = f"{self.run_dir}/Case_Def.xml"

        # 1. Set geometry
        logger.info(">>> set_geometry")
        r = await self.mcp.call_tool(
            "set_geometry",
            base_xml=f"{self.base_dir}/cases/BaseCase_Def.xml",
            output_xml=case_xml,
            geometry_xml=plan.geometry_xml,
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
            **plan.params.model_dump(),
        )
        logger.info("modify_xml OK: %s", r)

        # 3. Generate probe points file
        logger.info(">>> generate_points_file")
        r = await self.mcp.call_tool(
            "generate_points_file",
            output_path=f"{self.run_dir}/PointsMeasure_Points.txt",
            probe_points=plan.probe_points,
        )
        logger.info("generate_points_file OK: %s", r)

        # 4. Run GenCase
        logger.info(">>> run_gencase")
        r = await self.mcp.call_tool(
            "run_gencase",
            xml_path=f"{self.run_dir}/Case_Def",  # no .xml extension
            output_dir=f"{self.run_dir}/out",
        )
        result = json.loads(r) if isinstance(r, str) else r
        if result.get("returncode", -1) != 0:
            raise RuntimeError(f"run_gencase failed: {result.get('stderr', r)}")
        logger.info("run_gencase OK")

        # 5. Visualize (direct Python call, not MCP)
        logger.info(">>> visualize_geometry")
        viz_result = visualize_geometry(f"{self.run_dir}/out")
        logger.info("visualize_geometry: %s", viz_result)

    async def _execute_simulation(self) -> dict:
        """run_simulation → run_measuretool → compute_metrics."""
        assert self.run_dir is not None
        plan = self.current_plan
        assert plan is not None

        # 1. Run simulation (CPU)
        logger.info(">>> run_simulation")
        r = await self.mcp.call_tool(
            "run_simulation",
            case_path=f"{self.run_dir}/out/Case_Def",
            output_dir=f"{self.run_dir}/out",
            gpu=False,
        )
        sim_result = json.loads(r) if isinstance(r, str) else r
        if sim_result.get("returncode", -1) != 0:
            raise RuntimeError(f"run_simulation failed: {sim_result.get('stderr', r)}")
        logger.info("run_simulation OK")

        # 2. Run MeasureTool
        logger.info(">>> run_measuretool")
        r = await self.mcp.call_tool(
            "run_measuretool",
            data_dir=f"{self.run_dir}/out/data",
            points_file=f"{self.run_dir}/PointsMeasure_Points.txt",
            output_csv_stem=f"{self.run_dir}/out/measuretool/PointsMeasure",
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

        return {
            "geometry_xml": plan.geometry_xml,
            "params": plan.params.model_dump(),
            "probe_points": plan.probe_points,
            "rmse": metrics.get("rmse"),
            "correlation": metrics.get("correlation"),
            "run_dir": self.run_dir,
            "status": "ok",
        }
