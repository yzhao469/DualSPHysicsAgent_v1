# Code Structure — File Map and Function Dependencies

This document shows every code file, its functions/classes, and how they connect.

---

## Dependency Graph (High Level)

```
main.py
  ├── agents/workflow.py ─────────────── builds the workflow graph
  │     ├── agents/executors/planning.py
  │     ├── agents/executors/build.py
  │     ├── agents/executors/setup_review.py
  │     ├── agents/executors/sim.py
  │     ├── agents/executors/analyze.py
  │     └── agents/executors/results_loop.py
  ├── agents/simulation_agent.py ─────── creates the Agent + MCP tool
  └── agents/schemas.py ──────────────── shared data types

agents/executors/
  ├── setup_review.py
  │     ├── agents/utils/patch_utils.py ─── generate_patch(), merge_patch()
  │     ├── agents/utils/build_utils.py ─── rebuild_gencase_viz()
  │     ├── agents/utils/intent.py ──────── answer_question()
  │     └── agents/utils/skill_loader.py ── get_skill_content()
  ├── results_loop.py
  │     ├── agents/utils/intent.py ──────── answer_question()
  │     └── agents/utils/skill_loader.py ── get_postprocess_skill_content()
  ├── build.py
  │     └── agents/tools/visualize_geometry.py
  └── analyze.py
        └── agents/tools/visualize_geometry.py
```

---

## File-by-File Breakdown

### `main.py`

Entry point. Runs the async event loop.

```
main()
  ├── make_mcp_tool()           → MCPStdioTool (from simulation_agent.py)
  ├── make_simulation_agent()   → Agent (from simulation_agent.py)
  ├── AgentExecutor(agent)      → framework-provided executor
  ├── build_workflow(mcp, agent_executor, base_dir) → Workflow
  ├── input("> ")               → user scenario
  └── HITL loop:
        workflow.run(scenario) → stream
        process_events(stream) → responses or None
        while responses:
          workflow.run(responses=responses) → stream
          process_events(stream) → responses or None

process_events(stream)
  ├── async for event in stream:
  │     "request_info" → print summary, input(), collect response
  │     "executor_failed" → log error
  │     "failed" → log error
  └── check final state → return responses dict or None
```

---

### `agents/simulation_agent.py`

Creates the SimulationPlanner agent and MCP tool.

```
make_mcp_tool() → MCPStdioTool
  └── points to: .venv/bin/python mcp_server/server.py

make_simulation_agent() → Agent
  ├── loads Jinja template: agents/prompts/simulation_agent.j2
  ├── creates OpenAIChatClient (model: PLANNER_MODEL or gpt-4o)
  ├── creates SkillsProvider(skill_paths=skills/)
  └── returns Agent(client, instructions, response_format=SimulationPlan, context_providers)
```

---

### `agents/workflow.py`

Builds the workflow graph.

```
build_workflow(mcp, agent_executor, base_dir) → Workflow
  ├── instantiates 6 executors
  └── WorkflowBuilder:
        planning → agent_executor → build → setup_review
        setup_review → switch_case:
          ReviewResult(route="sim") → sim
          Default → planning (full_replan)
        sim → analyze → results_loop
        results_loop: terminal (no outgoing edges)
```

---

### `agents/schemas.py`

Shared data types. No logic, pure data.

```
PhysicsParams(BaseModel)        — 15 physics/execution parameters
SimulationPlan(BaseModel)       — geometry_xml, params, probe_points, reasoning
SetupReviewRequest(dataclass)   — summary: str
ResultsLoopRequest(dataclass)   — summary: str
ReviewResult(dataclass)         — route: "sim"|"full_replan", feedback: str
BuildResult(dataclass)          — run_dir, success, message
AnalysisResult(dataclass)       — run_dir, success, message, output_files
```

---

### `agents/executors/planning.py`

```
_list_datalake_files(base_dir) → list[str]
  └── glob datalake/**/*.xml, return relative paths

PlanningExecutor(Executor)
  ├── __init__(base_dir)
  │
  ├── @handler start(scenario: str, ctx)
  │     ├── _list_datalake_files()
  │     ├── resolve_datalake_file()        ← agents/utils/intent.py
  │     ├── _inject_datalake() if matched  ← reads XML, stores base_xml in state
  │     └── send_message(AgentExecutorRequest)
  │
  ├── @handler on_revision(review: ReviewResult, ctx)
  │     └── send_message(AgentExecutorRequest with revision text)
  │
  └── _inject_datalake(scenario, rel_path, abs_path, ctx) → str
        └── reads XML file, appends to scenario text
```

---

### `agents/executors/build.py`

```
BuildExecutor(Executor)
  ├── __init__(mcp, base_dir)
  │
  ├── @handler on_plan(result: AgentExecutorResponse, ctx)
  │     ├── SimulationPlan.model_validate_json(result.agent_response.text)
  │     ├── ctx.set_state("plan", plan.model_dump())
  │     ├── _build(plan_data, base_xml) → run_dir
  │     ├── ctx.set_state("run_dir", run_dir)
  │     └── send_message(BuildResult)
  │
  └── _build(plan_data, base_xml) → str
        ├── mcp.call_tool("set_geometry", ...)
        ├── mcp.call_tool("modify_xml", ...)
        ├── mcp.call_tool("generate_points_file", ...)
        ├── mcp.call_tool("run_gencase", ...)
        ├── visualize_geometry(run_dir/out)    ← agents/tools/visualize_geometry.py
        └── returns run_dir
```

---

### `agents/executors/setup_review.py`

```
_TOOLS = [...]   — 5 OpenAI function definitions (patch_and_rebuild, answer_question,
                    approve, manual_edit, replan)

_build_system_prompt(plan_data, run_dir) → str
  └── plan JSON + run_dir + role instructions

_format_plan_summary(plan: SimulationPlan) → str
  └── human-readable: reasoning + geometry XML + params table + probes

SetupReviewExecutor(Executor)
  ├── __init__(mcp, base_dir)
  │
  ├── @handler on_build_complete(result: BuildResult, ctx)
  │     ├── if failed → send_message(ReviewResult(full_replan))
  │     ├── format plan summary
  │     ├── init setup_review_history = [system_prompt]
  │     └── request_info(SetupReviewRequest(summary))     → HITL pause
  │
  ├── @response_handler on_user_reply(request, feedback, ctx)
  │     ├── check pending_manual_edit → rebuild_gencase_viz() if set
  │     ├── append user message to history
  │     └── while True:
  │           openai.chat.completions.create(history, tools)
  │           if text response → request_info(), return
  │           for each tool_call:
  │             "approve"           → send_message(ReviewResult(sim))
  │             "replan"            → send_message(ReviewResult(full_replan))
  │             "patch_and_rebuild" → _patch_and_rebuild()
  │             "manual_edit"       → set flag, request_info(), return
  │             "answer_question"   → answer_question()
  │
  └── _patch_and_rebuild(changes, plan_data, run_dir, ctx) → str
        ├── read Case_Def.xml from disk
        ├── generate_patch(xml, plan, changes)  ← agents/utils/patch_utils.py
        ├── apply via MCP: set_geometry, modify_xml, generate_points_file
        ├── merge_patch(plan_data, patch)        ← agents/utils/patch_utils.py
        ├── rebuild_gencase_viz(mcp, run_dir)    ← agents/utils/build_utils.py
        └── return success message
```

---

### `agents/executors/sim.py`

```
_has_gpu() → bool
  └── shutil.which("nvidia-smi")

SimExecutor(Executor)
  ├── __init__(mcp, base_dir)
  │
  └── @handler on_approved(trigger: ReviewResult, ctx)
        ├── get plan, run_dir from state
        ├── mcp.call_tool("run_simulation", case_path, output_dir, gpu)
        └── send_message(ReviewResult(route="sim"))    → to AnalyzeExecutor
```

---

### `agents/executors/analyze.py`

```
AnalyzeExecutor(Executor)
  ├── __init__(mcp, base_dir)
  │
  └── @handler on_sim_complete(trigger: ReviewResult, ctx)
        ├── mcp.call_tool("run_postprocess", partvtk, fluid)
        ├── mcp.call_tool("run_postprocess", partvtk, boundary)
        ├── mcp.call_tool("run_measuretool", ...)        (if points file exists)
        ├── mcp.call_tool("compute_metrics", ...)        (if ground truth exists)
        ├── visualize_geometry(particles_dir)
        └── send_message(AnalysisResult)
```

---

### `agents/executors/results_loop.py`

```
_TOOLS = [...]   — 4 OpenAI function definitions (run_postprocess,
                    run_python_analysis, answer_question, done)

_build_system_prompt(plan_data, run_dir, existing_files) → str
  └── run_dir + layout + params + file listing + postprocess skill content

_list_output_files(run_dir) → list[str]
  └── lists files in out/particles/, out/measuretool/, out/analysis/

ResultsLoopExecutor(Executor)
  ├── __init__(mcp, base_dir)
  │
  ├── @handler on_analysis_complete(result: AnalysisResult, ctx)
  │     ├── format results summary
  │     ├── _list_output_files()
  │     ├── init results_loop_history = [system_prompt]
  │     └── request_info(ResultsLoopRequest(summary))    → HITL pause
  │
  └── @response_handler on_user_reply(request, feedback, ctx)
        ├── append user message to history
        └── while True:
              openai.chat.completions.create(history, tools)
              if text response → request_info(), return
              for each tool_call:
                "done"                → yield_output({...}), return
                "run_postprocess"     → mcp.call_tool("run_postprocess", ...)
                "run_python_analysis" → print code, mcp.call_tool("run_analysis", ...)
                "answer_question"     → answer_question()
```

---

### `agents/utils/patch_utils.py`

```
PATCH_SYSTEM_PROMPT = "..."   — instructs LLM to return partial JSON patch

generate_patch(current_xml, plan_data, feedback) → dict
  ├── builds user content: plan JSON + XML + skill content + instruction
  ├── openai.chat.completions.create(PATCH_MODEL, json_mode)
  └── returns parsed JSON dict (only changed keys)

merge_patch(plan_data, patch) → dict
  └── merges geometry_xml, params, probe_points into plan_data (mutates)
```

---

### `agents/utils/build_utils.py`

```
rebuild_gencase_viz(mcp, run_dir) → None
  ├── mcp.call_tool("run_gencase", xml_path, output_dir)
  └── visualize_geometry(run_dir/out)    ← agents/tools/visualize_geometry.py
```

---

### `agents/utils/intent.py`

```
resolve_datalake_file(scenario, available_files) → str | None
  ├── openai.chat.completions.create(INTENT_MODEL, json_mode)
  │     system: file list + resolver instructions
  │     user: scenario text
  └── returns matched file path or None

answer_question(question, plan_context) → str
  ├── openai.chat.completions.create(INTENT_MODEL, temp=0.3)
  │     system: plan context + XML skill content
  │     user: question
  └── returns answer text
```

---

### `agents/utils/skill_loader.py`

```
_SKILLS_ROOT = skills/

_load_skill_dir(skill_dir) → str
  └── reads SKILL.md + all *.md files, joins with "---" separators

get_skill_content() → str           (cached)
  └── _load_skill_dir(dualsphysics-xml/)

get_postprocess_skill_content() → str  (cached)
  └── _load_skill_dir(dualsphysics-postprocess/)
```

---

### `agents/tools/visualize_geometry.py`

```
_is_wsl() → bool
  └── checks platform.uname().release for "microsoft"

_find_vtk_file(vtk_dir) → Path | None
  └── finds *_All.vtk, then *_Actual.vtk, then any non-_Dp.vtk

_open_image(png_path)
  ├── WSL: wslpath -w + cmd.exe /c start
  └── Linux: xdg-open | macOS: open

visualize_geometry(vtk_dir) → str
  ├── _find_vtk_file()
  ├── pyvista offscreen render → PNG (colored by Mk if available)
  ├── _open_image()
  └── returns confirmation message
```

---

## Call Flow Diagram

```
User types scenario
    │
    ▼
main.py::main()
    │
    ├─► PlanningExecutor::start()
    │       ├─► intent.py::resolve_datalake_file()  ···LLM call (gpt-4o-mini)
    │       └─► sends AgentExecutorRequest
    │
    ├─► AgentExecutor (framework)  ···LLM call (gpt-4o, structured output)
    │       └─► returns AgentExecutorResponse
    │
    ├─► BuildExecutor::on_plan()
    │       ├─► MCP: set_geometry, modify_xml, generate_points_file, run_gencase
    │       ├─► visualize_geometry()  ···pyvista render
    │       └─► sends BuildResult
    │
    ├─► SetupReviewExecutor::on_build_complete()
    │       └─► request_info() ··· HITL PAUSE ···
    │                                │
    │   User types feedback ◄────────┘
    │       │
    │       ▼
    │   SetupReviewExecutor::on_user_reply()
    │       ├─► OpenAI function calling  ···LLM call (gpt-4o-mini)
    │       ├─► may call: generate_patch()  ···LLM call (gpt-4o)
    │       ├─► may call: answer_question()  ···LLM call (gpt-4o-mini)
    │       ├─► may loop (request_info → user reply → on_user_reply)
    │       └─► eventually: sends ReviewResult(route="sim")
    │
    ├─► SimExecutor::on_approved()
    │       └─► MCP: run_simulation
    │
    ├─► AnalyzeExecutor::on_sim_complete()
    │       ├─► MCP: run_postprocess (partvtk x2), run_measuretool, compute_metrics
    │       ├─► visualize_geometry()
    │       └─► sends AnalysisResult
    │
    └─► ResultsLoopExecutor::on_analysis_complete()
            └─► request_info() ··· HITL PAUSE ···
                                     │
        User types request ◄─────────┘
            │
            ▼
        ResultsLoopExecutor::on_user_reply()
            ├─► OpenAI function calling  ···LLM call (gpt-4o)
            ├─► may call: MCP run_postprocess
            ├─► may call: MCP run_analysis (prints code first)
            ├─► may call: answer_question()  ···LLM call (gpt-4o-mini)
            ├─► may loop (request_info → user reply → on_user_reply)
            └─► eventually: yield_output() → workflow complete
```
