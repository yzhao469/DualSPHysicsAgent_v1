# Workflow Detail — How the Agent Works End-to-End

This document describes every step of the DualSPHysics MAF agent workflow, including
what data is passed between stages, what context each LLM call receives, and how
conversation memory is managed.

---

## Overview

The workflow has 5 phases:

1. **Planning** — user scenario → LLM reasoning → SimulationPlan JSON
2. **Build** — deterministic: XML → GenCase → pyvista visualization (no LLM)
3. **Setup Review** — user reviews plan + viz via LLM tool-use conversation loop
4. **Simulation + Default Post-Processing** — solver + PartVTK + MeasureTool (no LLM)
5. **Results Loop** — user interacts with results via LLM tool-use conversation loop

```
User scenario (string)
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: PLANNING                                              │
│  PlanningExecutor → AgentExecutor                               │
│                                                                 │
│  LLM calls: 1 (GPT-4o, structured output)                      │
│  Possible LLM calls: 1 (GPT-4o-mini, datalake file resolution) │
└─────────────────────────────────────────────────────────────────┘
     │  AgentExecutorResponse (contains SimulationPlan JSON)
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: BUILD (deterministic, no LLM)                         │
│  BuildExecutor                                                  │
│                                                                 │
│  MCP calls: set_geometry → modify_xml → generate_points         │
│             → run_gencase → visualize_geometry (pyvista)         │
└─────────────────────────────────────────────────────────────────┘
     │  BuildResult {run_dir, success, message}
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: SETUP REVIEW (LLM tool-use loop)                      │
│  SetupReviewExecutor                                            │
│                                                                 │
│  LLM calls: N per conversation turn (GPT-4o-mini + tools)      │
│  Possible sub-LLM calls: generate_patch (GPT-4o),              │
│                           answer_question (GPT-4o-mini)         │
│  Loop continues until user approves or replans                  │
└─────────────────────────────────────────────────────────────────┘
     │  ReviewResult {route: "sim"} or {route: "full_replan"}
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 4: SIMULATION + DEFAULT POST-PROCESSING (no LLM)         │
│  SimExecutor → AnalyzeExecutor                                  │
│                                                                 │
│  MCP calls: run_simulation → partvtk (fluid) → partvtk (bound) │
│             → run_measuretool → compute_metrics → visualize     │
└─────────────────────────────────────────────────────────────────┘
     │  AnalysisResult {run_dir, success, message, output_files}
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 5: RESULTS LOOP (LLM tool-use loop, terminal)            │
│  ResultsLoopExecutor                                            │
│                                                                 │
│  LLM calls: N per turn (GPT-4o + tools)                         │
│  Possible sub-LLM calls: answer_question (GPT-4o-mini)          │
│  Loop continues until user says "done"                          │
└─────────────────────────────────────────────────────────────────┘
     │  yield_output → workflow complete
     ▼
  Terminal
```

---

## Phase 1: Planning

### Step 1a: PlanningExecutor receives scenario

**Input**: User's natural-language string (e.g., "Simulate a debris flow...").

**Datalake detection**:
- Lists all XML files in `datalake/` directory
- Calls `resolve_datalake_file()` (GPT-4o-mini, single-turn, JSON mode)
  - **System prompt**: file-reference resolver + list of available files
  - **User message**: the scenario text
  - **Output**: `{"file": "datalake/MyCase.xml"}` or `{"file": null}`
- If a file is matched, reads the XML and appends it to the scenario text
- Stores `base_xml` path in workflow state (otherwise uses `cases/BaseCase_Def.xml`)

**Output**: `AgentExecutorRequest(messages=[Message("user", text=scenario)])`

### Step 1b: AgentExecutor generates SimulationPlan

**Model**: GPT-4o (via `PLANNER_MODEL` env var)

**Instructions**: `agents/prompts/simulation_agent.j2` — tells the LLM to:
1. Call `load_skill("dualsphysics-xml")` for core reference material
2. Call `read_skill_resource(...)` for drawing primitives, examples, transforms
3. Design geometry, choose physics params, place probes
4. Return `SimulationPlan` JSON (enforced via `response_format`)

**Context provided via SkillsProvider** (progressive disclosure):
- `dualsphysics-xml/SKILL.md` — loaded on `load_skill` call
- Resource files loaded on demand via `read_skill_resource`
- The LLM chooses which resources to load based on the scenario

**Structured output schema** (`SimulationPlan`):
```json
{
  "geometry_xml": "<geometry>...</geometry>",
  "params": { "rhop0": 1500, "visco_nn": 0.1, ... },
  "probe_points": [[1.0, 1.0, 0.1], ...],
  "reasoning": "Brief explanation"
}
```

**Output**: `AgentExecutorResponse` containing the JSON text.

---

## Phase 2: Build (deterministic)

### BuildExecutor

**Trigger**: `AgentExecutorResponse` (auto, no review gate).

**Steps**:
1. Parses `SimulationPlan` from agent response text
2. Stores `plan` dict in workflow state via `ctx.set_state("plan", ...)`
3. Creates timestamped run directory: `runs/run_YYYYMMDD_HHMMSS/`
4. MCP tool calls (all deterministic):
   - `set_geometry(base_xml, output_xml, geometry_xml)` — writes `Case_Def.xml`
   - `modify_xml(base_xml, output_xml, **params)` — updates physics params in XML
   - `generate_points_file(output_path, probe_points)` — writes `PointsMeasure_Points.txt`
   - `run_gencase(xml_path, output_dir)` — generates particle data in `out/`
5. `visualize_geometry(run_dir/out)` — pyvista renders `Case_Def_All.vtk` → PNG, opens image
6. Stores `run_dir` in workflow state

**Output**: `BuildResult(run_dir, success, message)`

---

## Phase 3: Setup Review (LLM tool-use loop)

### SetupReviewExecutor

**Trigger**: `BuildResult` from BuildExecutor.

**On entry** (`on_build_complete` handler):
1. If build failed → auto-route to `full_replan`
2. Formats plan summary (reasoning, geometry XML, params, probe points)
3. Initializes conversation history in workflow state:
   ```
   setup_review_history = [
     {"role": "system", "content": <system_prompt>}
   ]
   ```
4. Calls `ctx.request_info(SetupReviewRequest(summary=...))` → workflow pauses

**System prompt context** (`_build_system_prompt`):
- Full simulation plan as JSON
- Run directory path
- Role instructions (when to call each tool)

**On each user reply** (`on_user_reply` response_handler):
1. Checks for `pending_manual_edit` flag (resumes rebuild if set)
2. Appends user message to conversation history
3. Calls OpenAI with history + tool definitions (model: `INTENT_MODEL`, default `gpt-4o-mini`)
4. Processes response in a while loop:

```
while True:
  response = openai.chat.completions.create(messages=history, tools=_TOOLS)
  append assistant message to history

  if no tool_calls → text response:
    show text to user via request_info, return (wait for next reply)

  for each tool_call:
    "approve"         → send_message(ReviewResult(route="sim")), return
    "replan"          → send_message(ReviewResult(route="full_replan")), return
    "patch_and_rebuild" → execute patch, append tool result to history
    "manual_edit"     → pause workflow, set pending_manual_edit flag, return
    "answer_question" → call answer_question(), append result to history

  continue loop (LLM may chain more tool calls)
```

### Tool: `patch_and_rebuild`

When the LLM calls this tool, it triggers a sub-LLM call:

1. Reads current `Case_Def.xml` from disk
2. Calls `generate_patch()` (model: `PATCH_MODEL`, default `gpt-4o`):
   - **System prompt**: `PATCH_SYSTEM_PROMPT` — return JSON with only changed keys
   - **User message**: current plan JSON + current XML + skill reference + user instruction
   - **Output**: `{"geometry_xml": "...", "params": {"rhop0": 2000}}` (partial)
3. Applies patch via MCP tools: `set_geometry`, `modify_xml`, `generate_points_file`
4. Calls `merge_patch()` to update plan in workflow state
5. Calls `rebuild_gencase_viz()` — re-runs GenCase + reopens ParaView
6. Returns "Patch applied successfully" as tool result

### Tool: `manual_edit`

1. Stores the OpenAI tool_call ID in `pending_manual_edit` state
2. Shows file path to user via `request_info`
3. When user replies "done", rebuilds GenCase + viz, appends tool result to history

### Tool: `answer_question`

Calls `answer_question()` from `intent.py`:
- **Model**: GPT-4o-mini (via `INTENT_MODEL`)
- **System prompt**: plan context (JSON) + full XML skill content
- **User message**: the question
- Returns answer text as tool result

**Conversation memory**: The full message history (system + all user/assistant/tool messages)
is persisted in `ctx.set_state("setup_review_history", history)` between HITL pauses.

---

## Phase 4: Simulation + Default Post-Processing

### SimExecutor

**Trigger**: `ReviewResult(route="sim")` from SetupReviewExecutor.

1. Reads `plan` and `run_dir` from workflow state
2. Auto-detects GPU via `shutil.which("nvidia-smi")`
3. Calls `run_simulation(case_path, output_dir, gpu=True/False)` via MCP
4. Sends `ReviewResult(route="sim")` to AnalyzeExecutor

### AnalyzeExecutor (default mode only)

**Trigger**: `ReviewResult` from SimExecutor.

No LLM calls — purely deterministic:

1. **PartVTK (fluid)**: exports fluid particles as VTK with velocity, density, pressure
   ```
   run_postprocess(partvtk, ["-dirin", "out/data", "-savevtk", "out/particles/PartFluid",
                              "-onlytype:-all,+fluid", "-vars:+idp,+vel,+rhop,+press"])
   ```
2. **PartVTK (boundary)**: exports boundary particles
3. **MeasureTool**: extracts probe data to CSV (if `PointsMeasure_Points.txt` exists)
4. **compute_metrics**: compares with ground truth CSV (if it exists in `cases/ground_truth/`)
5. **ParaView**: opens fluid VTK results via pyvista

**Output**: `AnalysisResult(run_dir, success, message, output_files)`

---

## Phase 5: Results Loop (LLM tool-use loop, terminal)

### ResultsLoopExecutor

**Trigger**: `AnalysisResult` from AnalyzeExecutor.

**On entry** (`on_analysis_complete` handler):
1. Formats results summary (post-proc output, generated files)
2. Lists existing output files in `out/particles/`, `out/measuretool/`, `out/analysis/`
3. Initializes conversation history:
   ```
   results_loop_history = [
     {"role": "system", "content": <system_prompt>}
   ]
   ```
4. Calls `ctx.request_info(ResultsLoopRequest(summary=...))` → workflow pauses

**System prompt context** (`_build_system_prompt`):
- Run directory path
- Directory layout description
- Simulation parameters (TimeOut, TimeMax, probe points, full params JSON)
- List of existing output files (up to 50)
- Full post-processing skill content (`dualsphysics-postprocess/` skill files)
- Role instructions (which tool to use when, path conventions, CSV format notes)

**On each user reply** (`on_user_reply` response_handler):
1. Appends user message to history
2. Calls OpenAI with history + tool definitions (model: `ANALYSIS_MODEL`, default `gpt-4o`)
3. Same while-loop pattern as SetupReviewExecutor:

```
while True:
  response = openai.chat.completions.create(messages=history, tools=_TOOLS)
  append assistant message to history

  if no tool_calls → text response:
    show text to user via request_info, return

  for each tool_call:
    "done"                → yield_output({status, run_dir, params, probes}), return
    "run_postprocess"     → call MCP run_postprocess, append result to history
    "run_python_analysis" → print code to terminal, call MCP run_analysis, append result
    "answer_question"     → call answer_question(), append result to history

  continue loop
```

### Tool: `run_postprocess`

Calls the MCP `run_postprocess` tool with:
- `postprocess_tool`: one of partvtk, isosurface, computeforces, flowtool, boundaryvtk, floatinginfo, partvtkout, measuretool
- `args`: command-line arguments (all paths relative to run_dir)
- `cwd`: the run directory

Tool result returned to LLM: "OK — N output files: file1, file2" or "FAILED: error"

### Tool: `run_python_analysis`

1. **Prints code to terminal** before execution (user can see what the LLM wrote)
2. Calls MCP `run_analysis` with:
   - `python_code`: the Python script
   - `work_dir`: `{run_dir}/out/analysis/` (scripts run here as cwd)
3. Tool result: "OK\nGenerated: plot.png\nOutput: ..." or "FAILED: error"

### Tool: `answer_question`

Same as in SetupReviewExecutor — calls `answer_question()` from `intent.py`.

**Conversation memory**: Full OpenAI message history persisted in
`ctx.set_state("results_loop_history", history)`. This enables multi-turn analysis:
- User: "plot velocity over time" → LLM generates Python
- User: "zoom into 0-2s" → LLM remembers previous code, generates updated version

---

## Workflow State Keys

These keys are stored in `WorkflowContext` state and persist across executors:

| Key | Set by | Used by | Contents |
|-----|--------|---------|----------|
| `plan` | BuildExecutor | SetupReview, SimExecutor, ResultsLoop | `SimulationPlan.model_dump()` dict |
| `run_dir` | BuildExecutor | SetupReview, SimExecutor, AnalyzeExecutor, ResultsLoop | Absolute path to run directory |
| `base_xml` | PlanningExecutor | BuildExecutor | Path to base XML (datalake or default) |
| `setup_review_history` | SetupReviewExecutor | SetupReviewExecutor | OpenAI message history list |
| `pending_manual_edit` | SetupReviewExecutor | SetupReviewExecutor | Tool call ID (str) or False |
| `results_loop_history` | ResultsLoopExecutor | ResultsLoopExecutor | OpenAI message history list |

---

## LLM Call Summary

| Where | Model | Purpose | Context Given |
|-------|-------|---------|---------------|
| PlanningExecutor | GPT-4o-mini | Datalake file resolution | Available file list + scenario |
| AgentExecutor | GPT-4o | Generate SimulationPlan | Jinja prompt + SkillsProvider (progressive) |
| SetupReviewExecutor | GPT-4o-mini | Tool-use routing | Plan JSON + run_dir + conversation history |
| SetupReview → `patch_and_rebuild` | GPT-4o | Generate XML patch | Current XML + plan + skill content + instruction |
| SetupReview → `answer_question` | GPT-4o-mini | Answer questions | Plan JSON + XML skill content |
| ResultsLoopExecutor | GPT-4o | Tool-use routing + analysis | Params + file listing + postprocess skill + conversation history |
| ResultsLoop → `answer_question` | GPT-4o-mini | Answer questions | Plan JSON + XML skill content |

---

## HITL Event Loop (main.py)

```python
# Simplified flow
scenario = input()
stream = workflow.run(scenario, stream=True)
responses = await process_events(stream)  # prints summaries, collects input()

while responses is not None:
    stream = workflow.run(responses=responses, stream=True)
    responses = await process_events(stream)

# process_events handles:
#   - "request_info" events → print summary, prompt user, collect response
#   - "executor_failed" events → log error
#   - "failed" events → log error
#   - final state IDLE_WITH_PENDING_REQUESTS → return responses dict
#   - final state complete → print outputs, return None
```

The `SetupReviewRequest` and `ResultsLoopRequest` dataclasses both have a single
`summary` field. `main.py` prints `req_data.summary` directly to the terminal.
