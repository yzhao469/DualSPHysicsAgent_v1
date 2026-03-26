# API Usage — Chat Completions vs Responses API by Stage

This document maps every OpenAI API call in the workflow to its specific API
surface (**Chat Completions** or **Responses API**), the model used, and why
that API was chosen.

---

## Quick Reference

| Stage | API | Model (default) | File | Line |
|-------|-----|------------------|------|------|
| Datalake file resolution | Chat Completions | `gpt-4o-mini` | `agents/utils/intent.py` | `resolve_datalake_files()` |
| Planning (SimulationPlan) | Chat Completions (via agent_framework) | `gpt-4o` | `agents/simulation_agent.py` | `make_simulation_agent()` |
| Setup Review (tool-use loop) | **Responses API** | `gpt-4o-mini` | `agents/executors/plan_and_build.py` | `on_user_reply()` |
| Setup Review → `patch_and_rebuild` | Chat Completions | `gpt-4o` | `agents/utils/patch_utils.py` | `generate_patch()` |
| Setup Review → `answer_question` | Chat Completions | `gpt-4o-mini` | `agents/utils/intent.py` | `answer_question()` |
| Results Loop (tool-use loop) | **Chat Completions** | `gpt-4o` | `agents/executors/analyze.py` | `on_user_reply()` |
| Results Loop → `patch_and_rerun` | Chat Completions | `gpt-4o` | `agents/utils/script_utils.py` | `generate_script_patch()` |
| Results Loop → `answer_question` | Chat Completions | `gpt-4o-mini` | `agents/utils/intent.py` | `answer_question()` |

---

## Detailed Breakdown

### 1. Datalake File Resolution — Chat Completions

**When**: At the very start, before planning, only if there are files in the
`datalake/` directory.

**File**: `agents/utils/intent.py → resolve_datalake_files()`

```python
response = await client.chat.completions.create(
    model=os.getenv("INTENT_MODEL", "gpt-4o-mini"),
    temperature=0,
    response_format={"type": "json_object"},
    messages=[
        {"role": "system", "content": system},  # file list + resolver instructions
        {"role": "user", "content": scenario},   # user's scenario text
    ],
)
```

**API choice**: Chat Completions with JSON mode. This is a single-turn,
stateless call — no conversation history, no tool use. JSON mode ensures
a parseable `{"files": [...]}` response.

---

### 2. Planning (SimulationPlan Generation) — Chat Completions via Agent Framework

**When**: After datalake resolution, the `AgentExecutor` drives the
`SimulationPlanner` agent.

**File**: `agents/simulation_agent.py → make_simulation_agent()`

```python
client = OpenAIChatClient(model_id=os.getenv("PLANNER_MODEL", "gpt-4o"))

return Agent(
    client=client,
    instructions=instructions,         # Jinja-rendered system prompt
    default_options={"response_format": SimulationPlan},  # structured output
    context_providers=[skills_provider],  # SkillsProvider for tool-based skill loading
)
```

**API choice**: The `agent_framework`'s `OpenAIChatClient` wraps the **Chat
Completions API** internally. It uses:
- **Structured output** (`response_format`) to enforce the `SimulationPlan`
  Pydantic schema.
- **Tool calls** for `load_skill` and `read_skill_resource` — the
  `SkillsProvider` registers these as tools so the LLM can fetch reference
  material on demand (progressive disclosure).

The framework manages the multi-turn tool-call loop automatically: the agent
calls `load_skill("dualsphysics-xml")`, gets the SKILL.md content back, calls
`read_skill_resource(...)` for additional files, then produces the final
structured JSON response.

---

### 3. Setup Review — Responses API

**When**: After the build pipeline succeeds (or fails), the user enters an
interactive review loop.

**File**: `agents/executors/plan_and_build.py → on_user_reply()`

```python
response = await client.responses.create(
    model=os.getenv("INTENT_MODEL", "gpt-4o-mini"),
    temperature=0,
    input=history,          # Responses API input format
    instructions=instructions,  # separate from history (not a system message)
    tools=_TOOLS,           # Responses API tool format
)
```

**API choice**: The **Responses API** (`client.responses.create`). This is the
only stage that uses the Responses API. Key differences from Chat Completions:

| Aspect | Responses API (Setup Review) | Chat Completions (elsewhere) |
|--------|------------------------------|------------------------------|
| Instructions | Separate `instructions` parameter | `{"role": "system"}` in messages |
| History items | `{"type": "message", "role": "user", "content": [{"type": "input_text", ...}]}` | `{"role": "user", "content": "..."}` |
| Assistant output | `{"type": "message", "role": "assistant", "content": [{"type": "output_text", ...}]}` | `{"role": "assistant", "content": "..."}` |
| Tool calls | `{"type": "function_call", "id": ..., "call_id": ..., "name": ..., "arguments": ...}` | Nested in `message.tool_calls[].function` |
| Tool results | `{"type": "function_call_output", "call_id": ..., "output": ...}` | `{"role": "tool", "tool_call_id": ..., "content": ...}` |
| Tool definitions | `{"type": "function", "name": ..., "parameters": ...}` (flat) | `{"type": "function", "function": {"name": ..., "parameters": ...}}` (nested) |
| Image support | `{"type": "input_image", "image_url": "data:...;base64,..."}` | Via `image_url` content parts |

**Why Responses API here?** The setup review requires:
- **Image input** — datalake reference images and generated visualizations can
  be injected as `input_image` items in the conversation.
- **Separated instructions** — the `instructions` parameter is rebuilt
  dynamically (via `_refresh_instructions()`) when the build status changes
  (e.g., after a recovery failure), without modifying the conversation history.

#### Tool definitions (Responses API format)

```python
_TOOLS = [
    {
        "type": "function",
        "name": "patch_and_rebuild",     # flat — name at top level
        "description": "...",
        "parameters": { ... },
    },
    {
        "type": "function",
        "name": "approve",
        ...
    },
    # also: answer_question, manual_edit, get_reference, replan
]
```

#### History helper functions

The setup review has dedicated helper functions for building Responses API
history items:

- `_user_message(text)` — wraps text in `input_text`
- `_user_message_with_images(text, images)` — `input_text` + `input_image` items
- `_assistant_message(text)` — wraps text in `output_text`
- `_function_call_item(fc)` — serializes a function call from the response
- `_function_call_output(call_id, output)` — builds a tool result item

#### Sub-LLM calls triggered by setup review tools

When the setup review LLM calls `patch_and_rebuild`, it triggers a **separate
Chat Completions call**:

```python
# agents/utils/patch_utils.py → generate_patch()
response = await client.chat.completions.create(
    model=os.getenv("PATCH_MODEL", "gpt-4o"),
    temperature=0,
    response_format={"type": "json_object"},
    messages=[
        {"role": "system", "content": PATCH_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},  # XML + plan + skill + instruction
    ],
)
```

When it calls `answer_question`, another Chat Completions call:

```python
# agents/utils/intent.py → answer_question()
response = await client.chat.completions.create(
    model=os.getenv("INTENT_MODEL", "gpt-4o-mini"),
    temperature=0.3,
    messages=[
        {"role": "system", "content": plan_context + skill_content},
        {"role": "user", "content": question},
    ],
)
```

---

### 4. Results Loop — Chat Completions

**When**: After the simulation runs and default post-processing completes, the
user enters an interactive analysis loop.

**File**: `agents/executors/analyze.py → on_user_reply()`

```python
response = await client.chat.completions.create(
    model=os.getenv("ANALYSIS_MODEL", "gpt-4o"),
    temperature=0,
    messages=history,    # Chat Completions format, includes system message
    tools=_TOOLS,        # Chat Completions tool format
)
```

**API choice**: **Chat Completions** (`client.chat.completions.create`). Uses
a system message in the history array, standard message roles, and the nested
tool definition format.

#### Tool definitions (Chat Completions format)

```python
_TOOLS = [
    {
        "type": "function",
        "function": {                     # nested — function object
            "name": "patch_and_rerun",
            "description": "...",
            "parameters": { ... },
        },
    },
    # also: run_python_analysis, manual_edit, answer_question,
    #        get_reference, revise_setup, done
]
```

#### Sub-LLM calls triggered by results loop tools

When `patch_and_rerun` is called:

```python
# agents/utils/script_utils.py → generate_script_patch()
response = await client.chat.completions.create(
    model=os.getenv("PATCH_MODEL", "gpt-4o"),
    temperature=0,
    messages=[
        {"role": "system", "content": PATCH_SCRIPT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},  # script + plan + skill + instruction
    ],
)
```

---

## Summary: Why Two Different APIs?

The codebase uses the **Responses API** for the setup review and **Chat
Completions** for everything else. The key reasons:

1. **Responses API advantages** (used in setup review):
   - Cleaner `instructions` parameter — can be dynamically updated (e.g., after
     build recovery failures) without touching conversation history.
   - Native `input_image` support — datalake reference images are injected
     directly into the conversation.
   - Richer item-based history format.

2. **Chat Completions advantages** (used in results loop and utilities):
   - Simpler message format for conversation histories with system prompts.
   - Better for single-turn utility calls (file resolution, Q&A, patching).
   - Established, well-tested API for tool-use loops.

3. **Agent framework** (used in planning):
   - Wraps Chat Completions with structured output and SkillsProvider integration.
   - Handles multi-turn tool-call loops (load_skill, read_skill_resource)
     automatically.

---

## Environment Variables Controlling Models

| Variable | Default | Used By |
|----------|---------|---------|
| `PLANNER_MODEL` | `gpt-4o` | Agent planning (SimulationPlan generation) |
| `INTENT_MODEL` | `gpt-4o-mini` | Datalake resolution, setup review routing, Q&A |
| `PATCH_MODEL` | `gpt-4o` | XML patch generation, script patch generation |
| `ANALYSIS_MODEL` | `gpt-4o` | Results loop (tool-use routing + analysis) |
