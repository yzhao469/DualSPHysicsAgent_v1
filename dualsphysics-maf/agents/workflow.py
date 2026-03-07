"""8-executor workflow graph for the DualSPHysics simulation pipeline.

Workflow graph:
  PlanningExecutor → AgentExecutor → ReviewExecutor
                                          │
                                5-way switch_case
                     ┌──────────┬─────────┼──────────┬───────────┐
                     ▼          ▼         ▼          ▼           ▼
                BuildExec   SimExec  PatchExec  ManualEditExec  PlanningExec
                (plan OK)  (viz OK) (LLM patch) (user edits)  (full replan)
                     │         │         │          │
                     │         │         └──────────┘
                     │         │         all → ReviewExecutor (viz review)
                     │         │
                     │         ▼
                     │    AnalyzeExec ──→ ReviewExecutor (results review)
                     │                         │
                     │                   AnalysisRequest → AnalyzeExec (loop)
                     │                   "done" → terminal output
                     │                   full_replan → PlanningExec
                     │
                     └──→ ReviewExecutor (viz review)
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
from agents.executors.manual_edit import ManualEditExecutor
from agents.executors.patch import PatchExecutor
from agents.executors.planning import PlanningExecutor
from agents.executors.review import ReviewExecutor
from agents.executors.sim import SimExecutor
from agents.schemas import AnalysisRequest, ManualEditRequest, PatchRequest, ReviewResult


def build_workflow(mcp: MCPStdioTool, agent_executor: AgentExecutor, base_dir: str) -> Workflow:
    """Construct the 8-executor workflow graph.

    Args:
        mcp: The MCP stdio tool for DualSPHysics tool calls.
        agent_executor: The AgentExecutor wrapping the SimulationPlanner agent.
        base_dir: Absolute path to the dualsphysics-maf project directory.

    Returns:
        A built Workflow ready to be run.
    """
    planning_exec = PlanningExecutor(base_dir=base_dir)
    review_exec = ReviewExecutor()
    build_exec = BuildExecutor(mcp=mcp, base_dir=base_dir)
    sim_exec = SimExecutor(mcp=mcp, base_dir=base_dir)
    patch_exec = PatchExecutor(mcp=mcp, base_dir=base_dir)
    manual_edit_exec = ManualEditExecutor(mcp=mcp)
    analyze_exec = AnalyzeExecutor(mcp=mcp, base_dir=base_dir)

    return (
        WorkflowBuilder(start_executor=planning_exec)
        .add_edge(planning_exec, agent_executor)
        .add_edge(agent_executor, review_exec)
        .add_switch_case_edge_group(
            review_exec,
            [
                Case(condition=lambda r: isinstance(r, ReviewResult) and r.route == "build", target=build_exec),
                Case(condition=lambda r: isinstance(r, ReviewResult) and r.route == "sim", target=sim_exec),
                Case(condition=lambda r: isinstance(r, PatchRequest), target=patch_exec),
                Case(condition=lambda r: isinstance(r, ManualEditRequest), target=manual_edit_exec),
                Case(condition=lambda r: isinstance(r, AnalysisRequest), target=analyze_exec),
                Default(target=planning_exec),  # full_replan or "done"
            ],
        )
        .add_edge(build_exec, review_exec)
        .add_edge(patch_exec, review_exec)
        .add_edge(manual_edit_exec, review_exec)
        .add_edge(sim_exec, analyze_exec)
        .add_edge(analyze_exec, review_exec)
        .build()
    )
