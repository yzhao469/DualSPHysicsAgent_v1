# Potential Improvements

Observations and suggestions for the DualSPHysics MAF agent, organized by priority.

---

## 1. Context Window Growth in Conversation Loops

**Problem**: Both `SetupReviewExecutor` and `ResultsLoopExecutor` store the full OpenAI
message history in workflow state. Each tool call adds 3 messages (user + assistant
with tool_calls + tool result). The `run_python_analysis` tool is particularly expensive
because the full Python code is stored as the tool arguments, and stdout/file listings
come back as tool results. After 10-15 analysis requests, the history could approach
the context limit, especially since the system prompt already contains the full
postprocess skill content.

**Suggestions**:
- Implement a sliding window or summarization strategy: after N turns, compress older
  tool results to summaries while keeping the last few turns intact
- Move the postprocess skill content out of the system prompt and into a tool
  (e.g., `get_reference(topic)`) that the LLM can call on demand — this alone saves
  thousands of tokens per turn
- Track token usage and warn/summarize when approaching limits
- Consider storing only the last N tool results in full, summarizing older ones to
  "Step 3: ran partvtk, generated 20 VTK files"

---

## 2. Error Recovery in the Build Phase

**Problem**: If BuildExecutor fails (e.g., invalid geometry XML from the LLM), it sends
`BuildResult(success=False)` to SetupReviewExecutor, which auto-routes to `full_replan`.
This throws away the entire plan and restarts from scratch. But the failure is often a
minor XML syntax issue that could be fixed.

**Suggestions**:
- Instead of auto-replanning on build failure, enter the SetupReview loop with the
  error message. The LLM can then call `patch_and_rebuild` to fix the issue
- Include the error message (GenCase stderr) in the system prompt so the LLM knows
  what went wrong
- Add a retry counter to prevent infinite loops

---

## 3. No Validation of LLM-Generated Patch

**Problem**: `generate_patch()` returns a JSON dict, and `_patch_and_rebuild` applies it
directly via MCP tools. If the LLM returns invalid geometry XML, the `set_geometry`
call may fail silently or produce broken output. The `merge_patch` function also mutates
`plan_data` before verifying the MCP calls succeeded.

**Suggestions**:
- Validate the patch before applying: check that `geometry_xml` is well-formed XML,
  params are numeric and within reasonable ranges, probe points are valid coordinates
- Only call `merge_patch` after all MCP calls succeed (currently it's called at the end,
  but a partial failure could leave state inconsistent)
- Add a rollback mechanism: save the original XML before patching, restore on failure

---

## 4. SimExecutor Has No Error Handling

**Problem**: If `run_simulation` fails (e.g., divergence, bad parameters), SimExecutor
raises a `RuntimeError` which becomes an `executor_failed` event. The workflow stops
with no recovery path.

**Suggestions**:
- Catch the error and route back to SetupReviewExecutor with the error details, so the
  user can adjust parameters and retry
- For common failure modes (CFL violation, particle explosion), include diagnostic
  suggestions in the error message

---

## 5. Visualization Is Fire-and-Forget

**Problem**: `visualize_geometry()` renders a PNG and opens it with the system viewer.
If pyvista fails (missing display, import error), it silently returns an error string
that's only logged. The user may not see the visualization but the workflow proceeds
as if they did.

**Suggestions**:
- Make visualization failure more visible — print a warning to the terminal
- Support a fallback: if pyvista is unavailable, just print the VTK file path and let
  the user open it in ParaView manually
- Consider saving screenshots to a predictable location and mentioning the path in the
  HITL prompt

---

## 6. Skill Content Is Loaded Eagerly into System Prompts

**Problem**: The ResultsLoopExecutor's system prompt includes the full postprocess skill
content (all markdown files concatenated). This is sent with every single OpenAI API
call in the conversation loop, even if the user is just asking "what does RMSE mean?"

**Suggestions**:
- Split the skill content into a `get_reference` tool that the LLM can call on demand
- The system prompt can mention available reference topics without including the full text
- This reduces cost per API call and leaves more room for conversation history

---

## 7. No Streaming of LLM Responses

**Problem**: Both conversation loops call `openai.chat.completions.create()` and wait
for the full response before showing anything to the user. For complex analysis planning,
this can mean several seconds of silence.

**Suggestions**:
- Use streaming (`stream=True`) for the text-response case (when the LLM generates a
  text reply without tool calls)
- Print tokens as they arrive for a more responsive experience
- Tool calls still need to be collected fully before execution

---

## 8. Duplicate `answer_question` Implementations

**Problem**: `answer_question()` in `intent.py` uses the XML skill content as context.
This works for SetupReviewExecutor (plan questions) but is suboptimal for
ResultsLoopExecutor (post-processing questions). In the results loop, the postprocess
skill content would be more relevant, but the function always loads the XML skill.

**Suggestions**:
- Add a `skill_type` parameter to `answer_question()` that selects which skill content
  to include (xml vs postprocess)
- Or let the calling executor pass the context explicitly instead of having
  `answer_question()` load it internally

---

## 9. Manual Edit Doesn't Update Plan State

**Problem**: When the user manually edits `Case_Def.xml` and the `manual_edit` tool
rebuilds gencase, the `plan` dict in workflow state is not updated to reflect the
user's changes. The plan state still contains the pre-edit geometry/params. If the
user later asks a question or the LLM references the plan, it will be stale.

**Suggestions**:
- After manual edit rebuild, re-parse the XML to extract the current geometry and params,
  then update the plan state
- Or at minimum, add a note to the conversation history that the plan state may be stale

---

## 10. No Persistence Across Runs

**Problem**: If the user closes the terminal and restarts, all workflow state is lost.
There's no way to resume a previous session or re-enter the results loop for an
existing run directory.

**Partial mitigation**: The `postprocess.sh` script is now saved in the run directory
as a durable artifact. Users can re-run it independently (`./postprocess.sh`) without
the agent. However, conversation history and workflow state are still lost.

**Suggestions**:
- Save workflow state (plan, run_dir, conversation history) to a JSON file in the
  run directory
- Add a "resume" mode to `main.py` that loads state from an existing run directory
  and enters the results loop directly
- This is especially valuable for long simulations where the user may want to come
  back later for analysis

---

## 11. Hardcoded Absolute Paths

**Problem**: `simulation_agent.py` uses `BASE = str(Path(__file__).resolve().parents[1])`
and constructs absolute paths for the MCP server command, skill paths, etc. The run
directories use absolute paths throughout. This makes the project non-portable.

**Suggestions**:
- Use relative paths where possible, especially in stored state
- Make the MCP server path configurable via environment variable
- Document the path assumptions clearly for deployment

---

## 12. Agent 2 and Optimization Loop (Future)

**Not yet implemented**: The architecture was designed to support a second agent that
tunes simulation parameters based on results (comparing against ground truth). This
would involve:

- Running the full pipeline with initial parameters
- Comparing results against `cases/ground_truth/PointsMeasure.csv`
- Using an optimization LLM to suggest parameter adjustments
- Re-running until metrics converge

**Prerequisites**:
- Generate ground truth CSV (full sim with default params, TimeMax=5.0)
- Define convergence criteria (RMSE threshold, max iterations)
- Design the feedback loop (which parameters to adjust, constraints)
