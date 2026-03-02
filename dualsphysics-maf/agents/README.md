# agents

Executors, workflow graph, schemas, and LLM integration for the simulation planning/review flow.

## Files in this folder

| File | Main function / logic |
|---|---|
| `__init__.py` | Package marker for the `agents` module. |
| `build_executor.py` | Deterministic build stage: applies geometry and params, generates probe points, runs GenCase, and creates geometry visualization. |
| `intent.py` | Classifies user feedback (`approve`/`revise`/`question`) and answers user questions during review loops. |
| `planning_executor.py` | Converts initial scenario text or revision feedback into an `AgentExecutorRequest` for the planner agent. |
| `review_executor.py` | HITL gate for plan review and post-visualization review; routes flow based on intent classification. |
| `schemas.py` | Pydantic/dataclass models for simulation inputs/outputs shared across workflow executors. |
| `sim_executor.py` | Deterministic simulation stage: runs solver, runs MeasureTool, computes metrics, and yields final output payload. |
| `simulation_agent.py` | Builds the planning agent and MCP tool binding, loading prompt template + XML skill reference. |
| `workflow.py` | Defines and wires the 5-executor workflow graph and switch/case transitions. |
