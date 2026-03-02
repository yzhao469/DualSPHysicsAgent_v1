"""5-executor workflow graph for the DualSPHysics simulation pipeline.

Workflow graph:
  PlanningExecutor → AgentExecutor → ReviewExecutor
                                          │
                                switch_case edges
                               ┌──────────┼──────────┐
                               ▼          ▼          ▼
                          BuildExec   SimExec   PlanningExec
                          (plan OK)   (viz OK)  (revision)
                               │
                               ▼
                          ReviewExecutor (viz review)
"""

from agent_framework import (
    AgentExecutor,
    Case,
    Default,
    MCPStdioTool,
    Workflow,
    WorkflowBuilder,
)

from agents.build_executor import BuildExecutor
from agents.planning_executor import PlanningExecutor
from agents.review_executor import ReviewExecutor
from agents.sim_executor import SimExecutor


def build_workflow(mcp: MCPStdioTool, agent_executor: AgentExecutor, base_dir: str) -> Workflow:
    """Construct the 5-executor workflow graph.

    Args:
        mcp: The MCP stdio tool for DualSPHysics tool calls.
        agent_executor: The AgentExecutor wrapping the SimulationPlanner agent.
        base_dir: Absolute path to the dualsphysics-maf project directory.

    Returns:
        A built Workflow ready to be run.
    """
    planning_exec = PlanningExecutor()
    review_exec = ReviewExecutor()
    build_exec = BuildExecutor(mcp=mcp, base_dir=base_dir)
    sim_exec = SimExecutor(mcp=mcp, base_dir=base_dir)

    return (
        WorkflowBuilder(start_executor=planning_exec)
        .add_edge(planning_exec, agent_executor)
        .add_edge(agent_executor, review_exec)
        .add_switch_case_edge_group(
            review_exec,
            [
                Case(condition=lambda r: r.approved and r.phase == "plan", target=build_exec),
                Case(condition=lambda r: r.approved and r.phase == "viz", target=sim_exec),
                Default(target=planning_exec),
            ],
        )
        .add_edge(build_exec, review_exec)
        .build()
    )
