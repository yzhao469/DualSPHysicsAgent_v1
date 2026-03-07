"""6-executor workflow graph for the DualSPHysics simulation pipeline.

Workflow graph:
  PlanningExecutor → AgentExecutor → BuildExecutor (auto, no gate)
                                          │
                                          ▼
                                  SetupReviewExecutor (LLM + tools loop)
                                     │           │
                              approve│           │replan
                                     ▼           ▼
                                SimExecutor   PlanningExecutor
                                     │
                                     ▼
                                AnalyzeExecutor (default post-proc only)
                                     │
                                     ▼
                                ResultsLoopExecutor (LLM + tools loop, terminal)
"""

from agent_framework import (
    AgentExecutor,
    Case,
    Default,
    MCPStdioTool,
    Workflow,
    WorkflowBuilder,
)

from agents.executors.analyze import AnalyzeExecutor
from agents.executors.build import BuildExecutor
from agents.executors.planning import PlanningExecutor
from agents.executors.results_loop import ResultsLoopExecutor
from agents.executors.setup_review import SetupReviewExecutor
from agents.executors.sim import SimExecutor
from agents.schemas import ReviewResult


def build_workflow(mcp: MCPStdioTool, agent_executor: AgentExecutor, base_dir: str) -> Workflow:
    """Construct the 6-executor workflow graph.

    Args:
        mcp: The MCP stdio tool for DualSPHysics tool calls.
        agent_executor: The AgentExecutor wrapping the SimulationPlanner agent.
        base_dir: Absolute path to the dualsphysics-maf project directory.

    Returns:
        A built Workflow ready to be run.
    """
    planning_exec = PlanningExecutor(base_dir=base_dir)
    build_exec = BuildExecutor(mcp=mcp, base_dir=base_dir)
    setup_review_exec = SetupReviewExecutor(mcp=mcp, base_dir=base_dir)
    sim_exec = SimExecutor(mcp=mcp, base_dir=base_dir)
    analyze_exec = AnalyzeExecutor(mcp=mcp, base_dir=base_dir)
    results_loop_exec = ResultsLoopExecutor(mcp=mcp, base_dir=base_dir)

    return (
        WorkflowBuilder(start_executor=planning_exec)
        .add_edge(planning_exec, agent_executor)
        .add_edge(agent_executor, build_exec)              # auto-build
        .add_edge(build_exec, setup_review_exec)
        .add_switch_case_edge_group(
            setup_review_exec,
            [
                Case(
                    condition=lambda r: isinstance(r, ReviewResult) and r.route == "sim",
                    target=sim_exec,
                ),
                Default(target=planning_exec),  # full_replan
            ],
        )
        .add_edge(sim_exec, analyze_exec)
        .add_edge(analyze_exec, results_loop_exec)
        # ResultsLoopExecutor is terminal — ends via yield_output
        .build()
    )
