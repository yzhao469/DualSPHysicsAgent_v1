# agents

Executors, workflow graph, schemas, and LLM integration for the simulation planning/review flow.

## Top-level files

| File | Description |
|---|---|
| `__init__.py` | Package marker for the `agents` module. |
| `schemas.py` | Pydantic/dataclass models shared across workflow executors. |
| `simulation_agent.py` | Builds the planning agent and MCP tool binding, loading prompt template + XML skill reference. |
| `workflow.py` | Defines and wires the 7-executor workflow graph and switch/case transitions. |

## Subfolders

### [`executors/`](executors/)

The 6 executor classes that implement the workflow stages.

| File | Description |
|---|---|
| `build.py` | Deterministic build stage: applies geometry and params, generates probe points, runs GenCase, and creates geometry visualization. |
| `review.py` | HITL gate for plan review and post-visualization review; routes flow based on intent classification. |
| `planning.py` | Converts initial scenario text or revision feedback into an `AgentExecutorRequest` for the planner agent. |
| `sim.py` | Deterministic simulation stage: runs solver, runs MeasureTool, computes metrics, and yields final output payload. |
| `patch.py` | LLM-driven targeted patching of current case XML. |
| `manual_edit.py` | HITL manual XML editing + rebuild. |

### [`utils/`](utils/)

Support modules shared across executors.

| File | Description |
|---|---|
| `build_utils.py` | Shared `rebuild_gencase_viz()` helper used by PatchExecutor and ManualEditExecutor. |
| `intent.py` | Classifies user feedback (`approve`/`agent_patch`/`manual_edit`/`question`/`full_replan`), answers user questions, and resolves datalake files. |

### [`prompts/`](prompts/)

Jinja2 templates for LLM prompts. See [`prompts/README.md`](prompts/README.md).

### [`tools/`](tools/)

Python tools called directly (not via MCP). See [`tools/README.md`](tools/README.md).
