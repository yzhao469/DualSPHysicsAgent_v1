"""3-executor workflow graph for the DualSPHysics simulation pipeline.

Workflow graph:
  PlanAndBuildExecutor ──→ AgentExecutor ──→ PlanAndBuildExecutor
       │ AgentExecutorRequest  →  agent        (on_plan: build + review)
       │ ReviewResult(sim)     →  SimExecutor
       │ ReviewResult(replan)  →  self         (on_revision)
       │
  SimExecutor → AnalyzeExecutor (default post-proc + results loop, terminal)
"""

from agent_framework import (
    AgentExecutor,
    AgentExecutorRequest,
    Case,
    Default,
    MCPStdioTool,
    Workflow,
    WorkflowBuilder,
)

from agents.executors.analyze import AnalyzeExecutor
from agents.executors.plan_and_build import PlanAndBuildExecutor
from agents.executors.sim import SimExecutor
from agents.schemas import ReviewResult


def build_workflow(mcp: MCPStdioTool, agent_executor: AgentExecutor, base_dir: str) -> Workflow:
    """Construct the 3-executor workflow graph.

    Args:
        mcp: The MCP stdio tool for DualSPHysics tool calls.
        agent_executor: The AgentExecutor wrapping the SimulationPlanner agent.
        base_dir: Absolute path to the dualsphysics-maf project directory.

    Returns:
        A built Workflow ready to be run.
    """
    plan_and_build = PlanAndBuildExecutor(mcp=mcp, base_dir=base_dir)
    sim = SimExecutor(mcp=mcp, base_dir=base_dir)
    analyze = AnalyzeExecutor(mcp=mcp, base_dir=base_dir)

    return (
        WorkflowBuilder(start_executor=plan_and_build)
        .add_switch_case_edge_group(
            plan_and_build,
            [
                Case(
                    condition=lambda r: isinstance(r, AgentExecutorRequest),
                    target=agent_executor,
                ),
                Case(
                    condition=lambda r: isinstance(r, ReviewResult) and r.route == "sim",
                    target=sim,
                ),
                Default(target=plan_and_build),  # full_replan
            ],
        )
        .add_edge(agent_executor, plan_and_build)  # AgentExecutorResponse → on_plan
        .add_edge(sim, analyze)
        # AnalyzeExecutor is terminal — ends via yield_output
        .build()
    )
