# Context Management — What the Model Sees at Each State

This document traces exactly what context (system prompt, conversation history,
tool definitions, images) each LLM call receives at every stage of the workflow.
It answers: **at each state, what did the model see?**

---

## Overview: Context Flow Through the Workflow

```
User scenario (string)
     │
     ▼
 ┌──────────────────────────────────────────────────────┐
 │ 1. Datalake Resolution (if files exist)              │
 │    Model sees: file list + scenario                  │
 │    Context: EPHEMERAL (single turn, discarded)       │
 └──────────────────────────────────────────────────────┘
     │
     ▼
 ┌──────────────────────────────────────────────────────┐
 │ 2. Planning (AgentExecutor)                          │
 │    Model sees: system prompt + scenario + skills     │
 │    Context: EPHEMERAL (agent framework manages)      │
 └──────────────────────────────────────────────────────┘
     │  SimulationPlan JSON → stored in workflow state
     ▼
 ┌──────────────────────────────────────────────────────┐
 │ 3. Build (deterministic, no LLM)                     │
 │    Writes: plan, run_dir, base_xml to workflow state │
 └──────────────────────────────────────────────────────┘
     │
     ▼
 ┌──────────────────────────────────────────────────────┐
 │ 4. Setup Review (multi-turn, HITL)                   │
 │    Model sees: instructions + conversation history   │
 │    Context: PERSISTED in workflow state               │
 │    (setup_review_history, setup_review_instructions)  │
 └──────────────────────────────────────────────────────┘
     │  On approve → simulation runs (no LLM)
     ▼
 ┌──────────────────────────────────────────────────────┐
 │ 5. Results Loop (multi-turn, HITL)                   │
 │    Model sees: system prompt + conversation history  │
 │    Context: PERSISTED in workflow state               │
 │    (results_loop_history)                             │
 └──────────────────────────────────────────────────────┘
     │  On "done" → workflow complete
     ▼
  Terminal
```

Key insight: **Context does NOT carry over between stages.** Each stage builds
its own context from scratch, using data stored in workflow state (plan JSON,
run_dir, etc.) — not from the previous stage's conversation history.

---

## Stage 1: Datalake File Resolution

**Trigger**: User scenario + datalake files exist in the `datalake/` directory.

**What the model sees**:

| Role | Content |
|------|---------|
| **System** | "You are a file-reference resolver..." + bulleted list of every file in `datalake/` (relative paths) + JSON output instructions |
| **User** | The raw user scenario string (e.g., "Simulate a debris flow...") |

**Context lifetime**: Single turn. The response (`{"files": ["datalake/foo.xml"]}`)
is consumed immediately. Nothing from this call persists into any conversation
history.

**What it does NOT see**: No skill content, no plan, no previous conversation.

---

## Stage 2: Planning (SimulationPlan Generation)

**Trigger**: User scenario (possibly enriched with datalake XML/image content).

**What the model sees**:

### System prompt (instructions)

Rendered from `agents/prompts/simulation_agent.j2`:

```
You are a DualSPHysics simulation planner. Given a natural-language scenario
description, you design the geometry, choose physics parameters, and place
measurement probes.

You MUST respond with a valid SimulationPlan JSON object...

## Workflow
Before generating your SimulationPlan, you MUST load the reference material:
1. Call load_skill("dualsphysics-xml") ...
2. Call read_skill_resource("dualsphysics-xml", "drawing-shapes.md") ...
3. Call read_skill_resource("dualsphysics-xml", "fill-and-modification.md") ...
4. Call read_skill_resource("dualsphysics-xml", "composition-patterns.md") ...
5. Optionally call read_skill_resource("dualsphysics-xml", "transforms-and-variables.md") ...
```

Plus the `SimulationPlan` JSON schema and detailed geometry/physics instructions.

### User message

One of:
- **Simple**: Just the scenario text.
- **With datalake XML**: Scenario + `### Existing Case XML` + full XML content.
- **With datalake images**: Scenario + `### Reference Image` text + image
  attachments (as multimodal `Content` objects).
- **With mesh files**: Scenario + `### Available Mesh File` + import instructions.

### Tools available (via SkillsProvider)

| Tool | What it returns |
|------|-----------------|
| `load_skill("dualsphysics-xml")` | SKILL.md — core reference (~4000 tokens): XML structure, physics parameters, material archetypes, probe placement, reasoning guidelines |
| `read_skill_resource("dualsphysics-xml", "drawing-shapes.md")` | All shape-creation commands: drawbox, drawsphere, drawcylinder, drawprism, drawfilestl, etc. |
| `read_skill_resource("dualsphysics-xml", "fill-and-modification.md")` | Fill operations, redraw commands, freedraw mode, layer creation |
| `read_skill_resource("dualsphysics-xml", "composition-patterns.md")` | Complete geometry examples for common scenarios (2D channels, slopes, dam breaks) |
| `read_skill_resource("dualsphysics-xml", "transforms-and-variables.md")` | Transforms (drawmove, drawrotate, drawscale), variables, reusable lists |

### Multi-turn context within planning

The agent framework manages the tool-call loop internally:

```
Turn 1: LLM calls load_skill("dualsphysics-xml")
         → Framework returns SKILL.md content
Turn 2: LLM calls read_skill_resource("dualsphysics-xml", "drawing-shapes.md")
         → Framework returns drawing-shapes.md content
Turn 3: LLM calls read_skill_resource(..., "fill-and-modification.md")
         → Framework returns fill-and-modification.md content
Turn 4: LLM calls read_skill_resource(..., "composition-patterns.md")
         → Framework returns composition-patterns.md content
Turn 5: LLM produces final SimulationPlan JSON (structured output)
```

Each turn accumulates: the model sees all previous tool calls and their results
in its context window. By the final turn, it has the full scenario + all
loaded skill content + all intermediate reasoning.

**Context lifetime**: Managed by the agent framework. Discarded after the
`AgentExecutorResponse` is returned. None of this conversation persists.

**What carries forward**: Only the `SimulationPlan` JSON (stored as
`ctx.set_state("plan", plan_data)`).

---

## Stage 3: Build (Deterministic, No LLM)

No model calls. Reads `plan` from workflow state and executes MCP tools:
`set_geometry` → `modify_xml` → `generate_points_file` → `run_gencase` → `visualize_geometry`.

**What carries forward**:
- `plan` (dict) — the SimulationPlan
- `run_dir` (str) — path to the timestamped run directory
- `base_xml` (str) — path to the base XML file
- `datalake_mesh_paths` (list) — paths to mesh files copied into run_dir
- `datalake_image_paths` (list) — paths to reference images for review

---

## Stage 4: Setup Review (Interactive Loop)

**API**: Responses API  
**Trigger**: Build completes (success or failure) → HITL pause.

### What the model sees on each call

#### `instructions` parameter (dynamic, rebuilt on changes)

Built by `_build_instructions()`:

```
You are a helpful assistant reviewing a DualSPHysics simulation setup.
The user has been shown the simulation plan and a visualization of the
particle geometry.

### Build Status
Build completed successfully.  (or "Build failed before review started.")

### Current Build Error          (only if failed)
<error message>

### Recovery Attempts            (only if failed)
0 of 3

### Current Simulation Plan
```json
{
  "geometry_xml": "<geometry>...</geometry>",
  "params": { "rhop0": 1500, ... },
  "probe_points": [[1.0, 0.0, 0.1], ...],
  "reasoning": "Brief explanation"
}
```

### Run Directory
/path/to/runs/run_20250325_120000

### Your Role
- If the build status is failed, do not call `approve` until rebuilt...
- If the user is happy, call `approve`...
- If the user wants changes, call `patch_and_rebuild`...
- ...
```

**Important**: The `instructions` are **separate from the conversation
history** (a Responses API feature). They are rebuilt dynamically when:
- A build recovery changes the error state
- The plan is patched (plan_data updated)

This means the model always sees the **current** plan and build status, even
across multiple HITL turns.

#### `input` parameter (conversation history)

The history grows across HITL turns. Format: Responses API items.

**Initial state** (after build, before first user reply):

```python
history = []
# If datalake images exist, they are pre-seeded:
history = [
    {
        "type": "message", "role": "user",
        "content": [
            {"type": "input_text", "text": "Reference image(s) from the datalake (datalake/3d_debris.jpg)..."},
            {"type": "input_image", "image_url": "data:image/jpeg;base64,/9j/4AAQ..."},
        ]
    },
    {
        "type": "message", "role": "assistant",
        "content": [{"type": "output_text", "text": "I can see the reference image(s)..."}]
    },
]
```

**After first user reply** (e.g., "make the channel wider"):

```python
history = [
    # ... datalake images (if any) ...
    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "make the channel wider"}]},
]
```

**After LLM calls `patch_and_rebuild`** and it succeeds:

```python
history = [
    # ... previous items ...
    {"type": "function_call", "id": "fc_abc", "call_id": "call_123", "name": "patch_and_rebuild", "arguments": "{\"changes\": \"widen channel to 6m\"}"},
    {"type": "function_call_output", "call_id": "call_123", "output": "Patch applied successfully. Visualization regenerated."},
]
```

**After LLM responds with text**:

```python
history = [
    # ... all previous items ...
    {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "I've widened the channel to 6m. The visualization has been updated."}]},
]
```

The full history is persisted in `ctx.set_state("setup_review_history", history)`
between HITL pauses.

#### Tools available

| Tool | What happens when called |
|------|--------------------------|
| `patch_and_rebuild` | Triggers a sub-LLM call (`generate_patch` via Chat Completions, GPT-4o) → applies MCP tools → rebuilds GenCase → returns success/error |
| `approve` | Checks for unresolved build errors → if clean, prompts user for final confirmation → routes to SimExecutor |
| `answer_question` | Triggers a sub-LLM call (Chat Completions, GPT-4o-mini) with plan context + XML skill content |
| `manual_edit` | Pauses workflow, shows file path, user edits, then rebuilds on resume |
| `get_reference` | Returns skill file content (no LLM call — reads from disk via `get_skill_topic()`) |
| `replan` | Routes to PlanAndBuildExecutor.on_revision for a fresh plan |

### Sub-LLM call context: `patch_and_rebuild` → `generate_patch()`

**What the patch model sees**:

| Role | Content |
|------|---------|
| **System** | `PATCH_SYSTEM_PROMPT` — instructions to return a partial JSON patch with only changed keys |
| **User** | `### Current Plan` (full plan JSON) + `### Current Case_Def.xml` (full XML file) + `### Reference Material` (entire XML skill bundle — SKILL.md + all resource files) + `### User Instruction` (the change request) |

This is a **single-turn, stateless call** — no conversation history. The entire
current state is passed in every time.

### Sub-LLM call context: `answer_question()`

| Role | Content |
|------|---------|
| **System** | Plan JSON + full XML skill content (or postprocess skill content) |
| **User** | The question text |

Also single-turn, stateless.

**What carries forward to Stage 5**: Only workflow state keys (`plan`,
`run_dir`, `script_path`). The setup review conversation history is **not**
used by the results loop.

---

## Stage 4b: Simulation + Default Post-Processing (No LLM)

SimExecutor runs the solver (`run_simulation` via MCP). AnalyzeExecutor
generates `postprocess.sh`, parses it, runs each command via MCP, optionally
computes metrics against ground truth.

**What carries forward**:
- `script_path` — path to postprocess.sh
- Updated `plan` data
- `run_dir` — unchanged

---

## Stage 5: Results Loop (Interactive Loop)

**API**: Chat Completions  
**Trigger**: Post-processing completes → HITL pause.

### What the model sees on each call

#### System message (in `history[0]`)

Built by `_build_results_system_prompt()`:

```
You are an expert DualSPHysics post-processing assistant. The simulation
has completed and default post-processing has been run.

### Run Directory
/path/to/runs/run_20250325_120000

### Directory Layout
  out/data/           — raw simulation .bi4 files
  out/particles/      — VTK exports (from default post-processing)
  out/measuretool/    — MeasureTool CSV outputs
  out/analysis/       — analysis output directory

### Simulation Parameters
  TimeOut (output interval): 0.1 s
  TimeMax: 2.0 s
  Probe points: [[1.0, 0.0, 0.1], ...]
  Full params: { "rhop0": 1500, ... }

### Existing Output Files
  - out/particles/PartFluid_0000.vtk
  - out/particles/PartFluid_0001.vtk
  - out/particles/PartBound_0000.vtk
  - out/measuretool/PointsMeasure.csv
  ...

### Current postprocess.sh
Path: /path/to/runs/run_.../postprocess.sh
```bash
#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="/path/to/bin/linux"
...
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data ...
"$BIN_DIR"/MeasureTool_linux64 ...
```

### Post-Processing Overview
<full postprocess skill content — SKILL.md + resource files>

### Detailed CLI References
For exact flag names, call `get_reference` with: partvtk, isosurface, ...

### Your Role
- Use `patch_and_rerun` to modify the script...
- Use `run_python_analysis` for ad-hoc analysis...
- Use `revise_setup` to go back to setup phase...
- When done, call `done`...
```

**Important**: The system message is **updated in-place** when `patch_and_rerun`
modifies the script. The updated script content replaces the old content in
`history[0]`, so the model always sees the latest script.

#### Conversation history (Chat Completions format)

**Initial state**:

```python
history = [
    {"role": "system", "content": <system prompt above>},
]
```

**After user says "add isosurface"**:

```python
history = [
    {"role": "system", "content": <system prompt>},
    {"role": "user", "content": "add isosurface"},
]
```

**After LLM calls `patch_and_rerun` and responds**:

```python
history = [
    {"role": "system", "content": <UPDATED system prompt with new script>},
    {"role": "user", "content": "add isosurface"},
    {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_xyz", "function": {"name": "patch_and_rerun", "arguments": "{\"changes\": \"add isosurface...\"}"}},
    ]},
    {"role": "tool", "tool_call_id": "call_xyz", "content": "Script execution results:\n  - OK partvtk: 21 files\n  - OK isosurface: 21 files"},
    {"role": "assistant", "content": "I've added IsoSurface to the post-processing pipeline. ..."},
]
```

The full history is persisted in `ctx.set_state("results_loop_history", history)`.

#### Tools available

| Tool | What happens when called |
|------|--------------------------|
| `patch_and_rerun` | Triggers a sub-LLM call (`generate_script_patch` via Chat Completions, GPT-4o) → writes new script → re-parses and re-executes via MCP → updates system prompt in history |
| `run_python_analysis` | Prints code to terminal → executes via MCP `run_analysis` → returns stdout/files/errors |
| `manual_edit` | Pauses workflow, shows script path, user edits, re-executes on resume |
| `answer_question` | Sub-LLM call (Chat Completions, GPT-4o-mini) with plan + postprocess skill content |
| `get_reference` | Returns skill file content from disk (no LLM) |
| `revise_setup` | Prompts for confirmation → routes back to PlanAndBuildExecutor for full replan |
| `done` | Yields final output, workflow terminates |

### Sub-LLM call context: `patch_and_rerun` → `generate_script_patch()`

| Role | Content |
|------|---------|
| **System** | `PATCH_SCRIPT_SYSTEM_PROMPT` — instructions to return the complete updated shell script |
| **User** | `### Current postprocess.sh` (full script) + `### Simulation Plan` (full plan JSON) + `### Post-Processing Reference` (entire postprocess skill bundle) + `### User Instruction` (the change request) |

Single-turn, stateless. The entire current state is provided each time.

---

## Context Isolation Summary

| From → To | What transfers | What does NOT transfer |
|-----------|---------------|----------------------|
| Datalake resolution → Planning | Matched file paths; XML/image content injected into scenario message | LLM conversation (discarded) |
| Planning → Build | `plan` (SimulationPlan dict), `base_xml`, `datalake_mesh_paths`, `datalake_image_paths` in workflow state | Agent conversation history (discarded) |
| Build → Setup Review | `plan`, `run_dir`, `base_xml`, `datalake_image_paths` from workflow state | No conversation history (fresh start) |
| Setup Review → Simulation | `plan`, `run_dir` from workflow state | Setup review conversation history stays in state but is not used downstream |
| Simulation → Results Loop | `plan`, `run_dir`, `script_path` from workflow state | No conversation history (fresh start); setup review history not read |
| Results Loop → (replan) Setup | `plan` (updated), revision feedback | Results loop conversation history stays in state but not used by setup review |

### Key Design Decisions

1. **No cross-stage conversation memory**: Each interactive stage (setup review,
   results loop) starts with a fresh conversation. Context is rebuilt from
   workflow state (plan JSON, file paths, script content) — not from previous
   conversations.

2. **Within-stage persistence**: Inside each HITL loop, the full conversation
   history is persisted in workflow state across user turns. This enables
   multi-turn interactions where the model remembers what was discussed.

3. **Dynamic context updates**: Both stages update their context during the
   conversation:
   - Setup review: `instructions` are rebuilt after build status changes.
   - Results loop: `history[0]` (system message) is updated when the script changes.

4. **Sub-LLM calls are stateless**: Every sub-call (`generate_patch`,
   `generate_script_patch`, `answer_question`) is a single-turn call with the
   full current state provided in the messages. They have no memory of previous
   sub-calls.

5. **Progressive disclosure in planning**: The planner agent doesn't receive all
   skill content upfront. It calls `load_skill` and `read_skill_resource` to
   fetch only what it needs, keeping the initial context small (~100 tokens for
   skill advertisements) and letting the model decide what reference material
   to load.
