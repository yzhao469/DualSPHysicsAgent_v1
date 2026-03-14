# DualSPHysics MAF — Project Notes for Claude

## Project Location
```
/home/danrong/projects/DualSPHysics_NN_v5.0.1/dualsphysics-maf/
```
Python venv: `.venv/`
Run with: `.venv/bin/python`

## Environment
- **Platform**: WSL2 (Linux on Windows)
- When opening files/images, use `cmd.exe /c start` via `wslpath -w` (see `visualize_geometry.py`)
- Prefer relative paths with working directory patterns over absolute paths

---

## Architecture (2026-03-14 — 3-Executor Workflow with LLM Tool-Use Loops)

**Core pattern**: LLM reasons only (returns structured JSON or uses function calling),
Python code orchestrates all MCP tool calls deterministically.

**Two HITL interaction points**, both using OpenAI function-calling conversation loops:
1. **PlanAndBuildExecutor** — plans, builds, and reviews setup (HITL loop #1)
2. **AnalyzeExecutor** — default post-proc + interactive analysis (HITL loop #2)

### Workflow Graph

```
  PlanAndBuildExecutor ──→ AgentExecutor ──→ PlanAndBuildExecutor
       │ AgentExecutorRequest  →  agent        (on_plan: build + review)
       │ ReviewResult(sim)     →  SimExecutor
       │ ReviewResult(replan)  →  self         (on_revision)
       │
  SimExecutor → AnalyzeExecutor (default post-proc + results loop, terminal)
```

### 3 Custom Executors (+1 Framework-Provided)

| # | Executor | ID | Trigger | Output |
|---|----------|----|---------|--------|
| 1 | `PlanAndBuildExecutor` | `plan_and_build` | `str` (scenario), `ReviewResult` (replan), or `AgentExecutorResponse` (build+review) | `AgentExecutorRequest` or `ReviewResult` |
| 2 | `AgentExecutor` (MAF) | — | `AgentExecutorRequest` | `AgentExecutorResponse` |
| 3 | `SimExecutor` | `sim` | `ReviewResult` | `ReviewResult` |
| 4 | `AnalyzeExecutor` | `analyze` | `ReviewResult` | terminal (`yield_output`) |

### HITL Mechanism

1. Executor calls `ctx.request_info(SetupReviewRequest(...))` or `ResultsLoopRequest(...)`
2. Workflow pauses; `main.py` event loop prints summary, prompts `input()`
3. `workflow.run(responses={request_id: user_reply})` resumes
4. Executor's `@response_handler` receives the reply, runs through LLM tool-use loop
5. LLM decides action via function calling (no separate intent classifier)

---

## File Inventory

### MCP Server (9 tools)
| File | Description |
|------|-------------|
| `mcp_server/config.py` | Path configuration (all binaries) |
| `mcp_server/server.py` | FastMCP server, 9 tools |
| `mcp_server/tools/_subprocess.py` | Shared async subprocess helper |
| `mcp_server/tools/_xml_utils.py` | `preprocess_xml()` — fixes XML quirks |
| `mcp_server/tools/xml_modifier.py` | Physics/execution parameter modification |
| `mcp_server/tools/set_geometry.py` | Geometry replacement tool |
| `mcp_server/tools/generate_points.py` | Probe points file generation |
| `mcp_server/tools/run_gencase.py` | Particle generation |
| `mcp_server/tools/run_simulation.py` | DualSPHysics solver |
| `mcp_server/tools/run_measuretool.py` | Probe data extraction |
| `mcp_server/tools/metrics.py` | RMSE/correlation |
| `mcp_server/tools/postprocess.py` | Generic wrapper: partvtk, isosurface, computeforces, etc. |
| `mcp_server/tools/run_analysis.py` | Python analysis script executor |

### Workflow + Agents
| File | Description |
|------|-------------|
| `agents/schemas.py` | `SimulationPlan`, `PhysicsParams`, `SetupReviewRequest`, `ResultsLoopRequest`, `ReviewResult` |
| `agents/simulation_agent.py` | SimulationPlanner Agent (GPT-4o + SkillsProvider) |
| `agents/workflow.py` | WorkflowBuilder: 3 executors + switch_case routing |
| `agents/executors/plan_and_build.py` | PlanAndBuildExecutor (planning + build + setup review HITL loop) |
| `agents/executors/sim.py` | SimExecutor (auto GPU detection) |
| `agents/executors/analyze.py` | AnalyzeExecutor (default post-processing + results loop HITL) |

### Utilities
| File | Description |
|------|-------------|
| `agents/utils/build_utils.py` | `rebuild_gencase_viz()` — shared by PlanAndBuildExecutor |
| `agents/utils/intent.py` | `resolve_datalake_file()` + `answer_question()` |
| `agents/utils/patch_utils.py` | `generate_patch()` + `merge_patch()` for LLM XML patching |
| `agents/utils/skill_loader.py` | `get_skill_content()` (xml) + `get_postprocess_skill_content()` |
| `agents/tools/visualize_geometry.py` | Pyvista VTK → PNG + system viewer (WSL2 compatible) |
| `agents/prompts/simulation_agent.j2` | Jinja template for SimulationPlanner instructions |

### Skill Files
| File | Description |
|------|-------------|
| `skills/dualsphysics-xml/SKILL.md` | XML structure, domain limits, 2D/3D rules, physics params, material archetypes, probes |
| `skills/dualsphysics-xml/drawing-shapes.md` | All shape-creation commands (boxes, spheres, cylinders, prisms, lines, triangles, external geometry) |
| `skills/dualsphysics-xml/fill-and-modification.md` | Fill operations, redraw commands, freedraw mode, multi-layer shells |
| `skills/dualsphysics-xml/transforms-and-variables.md` | Transform stack, variables, expressions, reusable lists, clipping, debugging |
| `skills/dualsphysics-xml/composition-patterns.md` | 11 complete geometry examples |
| `skills/dualsphysics-postprocess/SKILL.md` | Post-processing overview, patterns, analysis guide |
| `skills/dualsphysics-postprocess/partvtk-help.md` | PartVTK CLI reference |
| `skills/dualsphysics-postprocess/isosurface-help.md` | IsoSurface CLI reference |
| `skills/dualsphysics-postprocess/other-tools-help.md` | ComputeForces, FlowTool, BoundaryVTK, etc. |

### Other
| File | Description |
|------|-------------|
| `cases/BaseCase_Def.xml` | Base XML template |
| `cases/ground_truth/` | Ground truth CSVs (not yet generated) |
| `datalake/` | User-provided XML cases |
| `main.py` | Terminal workflow event loop + HITL |
| `gui.py` | Streamlit web GUI — chat + XML/script editors + file browser. Same workflow, thread+queue bridge. |
| `main_smoke.py` | Smoke test (bypasses workflow) |

---

## Tools

### Pre-processing (7 MCP tools)
| Tool | Purpose |
|------|---------|
| `set_geometry` | Replace `<geometry>` block |
| `modify_xml` | Modify physics/execution parameters (15 params) |
| `generate_points_file` | Generate probe points file |
| `run_gencase` | Generate particle configuration |
| `run_simulation` | Run DualSPHysics solver |
| `run_measuretool` | Probe data extraction |
| `compute_metrics` | RMSE/correlation calculation |

### Post-processing (2 MCP tools wrapping 8 CLI binaries)
| Tool | Purpose |
|------|---------|
| `run_postprocess` | Generic wrapper: partvtk, partvtkout, isosurface, computeforces, flowtool, boundaryvtk, floatinginfo, measuretool |
| `run_analysis` | Execute Python analysis scripts (numpy/matplotlib/pandas/pyvista) |

---

## Environment Variables
- `OPENAI_API_KEY` — required
- `PLANNER_MODEL` — SimulationPlanner model (default `gpt-4o`)
- `PATCH_MODEL` — patch LLM for XML changes (default `gpt-4o`)
- `INTENT_MODEL` — Q&A + datalake resolution (default `gpt-4o-mini`)
- `ANALYSIS_MODEL` — ResultsLoopExecutor model (default `gpt-4o`)

---

## Key Implementation Details

- **GPU auto-detection**: `shutil.which("nvidia-smi")` in SimExecutor
- **XML preprocessing**: `preprocess_xml()` fixes triple-dash comments, %-comments, unescaped `<`/`>` in attrs
- **MCP call pattern**: `mcp.call_tool("tool_name", **kwargs)` returns a string (JSON for dict-returning tools)
- **Visualization**: pyvista renders VTK → PNG offscreen, then opens with system viewer
- **Conversation memory**: SetupReview and ResultsLoop store OpenAI message history in workflow state (`setup_review_history`, `results_loop_history`)
- **PartVTK CSV format**: semicolon-separated, columns like `Idp;Pos.x;Pos.y;Pos.z;Vel.x;Vel.y;Vel.z;Rhop`
- **Python code visibility**: ResultsLoopExecutor prints LLM-generated Python code to terminal before execution
- `opentelemetry-semantic-conventions-ai` must be pinned to `==0.4.13`

---

## Next Steps

1. Generate ground truth CSV (full sim with default params, TimeMax=5.0)
2. Have domain expert expand material archetypes in skill file
3. Push to GitHub (hardcoded paths need attention)
4. Agent 2 + optimization loop
