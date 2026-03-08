"""ResultsLoopExecutor — LLM tool-use interactive post-processing loop.

Uses a postprocess.sh script as the shared artifact (analogous to
Case_Def.xml in the setup phase). The user and LLM collaborate on the
script: the LLM proposes changes, the executor re-parses and re-runs
commands via MCP for structured feedback.
"""

import json
import logging
import os

from openai import AsyncOpenAI

from agent_framework import (
    Executor,
    MCPStdioTool,
    WorkflowContext,
    handler,
    response_handler,
)

from agents.schemas import AnalysisResult, ResultsLoopRequest
from agents.utils.script_utils import (
    generate_script_patch,
    parse_script,
)
from agents.utils.skill_loader import get_postprocess_skill_content

logger = logging.getLogger(__name__)

# OpenAI function definitions for the results loop LLM
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "patch_and_rerun",
            "description": (
                "Modify the postprocess.sh script based on the user's request, "
                "then re-execute all commands. Use this to add, remove, or change "
                "post-processing steps (PartVTK, IsoSurface, ComputeForces, etc.)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "changes": {
                        "type": "string",
                        "description": "Description of what to change in the post-processing script.",
                    },
                },
                "required": ["changes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python_analysis",
            "description": (
                "Execute a Python script for ad-hoc data analysis (CSV parsing, "
                "computing derived quantities, plotting with matplotlib). "
                "The script runs with out/analysis/ as its working directory. "
                "Use relative paths: ../data/, ../particles/, ../measuretool/ "
                "to access other output directories. This is for one-off analysis "
                "not part of the main post-processing script."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of what the script does.",
                    },
                },
                "required": ["code", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manual_edit",
            "description": (
                "Let the user manually edit the postprocess.sh file directly. "
                "Use this when the user says they want to edit the script themselves."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "answer_question",
            "description": (
                "Answer a conceptual question about the simulation results, "
                "DualSPHysics, physics, or post-processing techniques. "
                "For questions that require reading data files, use "
                "run_python_analysis instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to answer.",
                    },
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "User is finished with the analysis. End the workflow.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _build_system_prompt(
    plan_data: dict, run_dir: str, script_path: str, script_text: str,
    existing_files: list[str],
) -> str:
    """Build the system prompt for the results loop LLM."""
    skill_text = get_postprocess_skill_content()
    params = plan_data.get("params", {})

    files_section = ""
    if existing_files:
        files_section = "\n### Existing Output Files\n" + "\n".join(
            f"  - {f}" for f in existing_files[:50]
        )

    return (
        "You are an expert DualSPHysics post-processing assistant. The simulation "
        "has completed and default post-processing has been run.\n\n"
        f"### Run Directory\n{run_dir}\n\n"
        "### Directory Layout\n"
        "  out/data/           — raw simulation .bi4 files\n"
        "  out/particles/      — VTK exports (from default post-processing)\n"
        "  out/measuretool/    — MeasureTool CSV outputs\n"
        "  out/analysis/       — analysis output directory\n\n"
        f"### Simulation Parameters\n"
        f"  TimeOut (output interval): {params.get('TimeOut', 0.1)} s\n"
        f"  TimeMax: {params.get('TimeMax', 5.0)} s\n"
        f"  Probe points: {plan_data.get('probe_points', [])}\n"
        f"  Full params: {json.dumps(params, indent=2)}\n"
        f"{files_section}\n\n"
        f"### Current postprocess.sh\n"
        f"Path: {script_path}\n"
        f"```bash\n{script_text}\n```\n\n"
        f"### Post-Processing Reference\n{skill_text}\n\n"
        "### Your Role\n"
        "- Use `patch_and_rerun` to modify the postprocess.sh script and re-execute it.\n"
        "- Use `run_python_analysis` for ad-hoc CSV parsing, metrics, and plotting.\n"
        "- Use `manual_edit` when the user wants to edit postprocess.sh themselves.\n"
        "- ALL post-processing tool changes go through the script.\n"
        "- Python scripts run with out/analysis/ as cwd. Use relative paths.\n"
        "- PartVTK CSV uses semicolon separator. Use numpy.genfromtxt with delimiter=';'.\n"
        "- In Python, use matplotlib with Agg backend for plots.\n"
        "- When the user is done (says 'done', 'exit', 'finished', etc.), call `done`.\n"
    )


def _list_output_files(run_dir: str) -> list[str]:
    """List existing output files in the run directory."""
    existing = []
    for subdir in ["out/particles", "out/measuretool", "out/analysis"]:
        full_dir = os.path.join(run_dir, subdir)
        if os.path.isdir(full_dir):
            for f in sorted(os.listdir(full_dir)):
                existing.append(os.path.join(subdir, f))
    return existing


class ResultsLoopExecutor(Executor):
    """LLM tool-use conversational loop for interactive post-processing."""

    def __init__(self, mcp: MCPStdioTool, base_dir: str) -> None:
        super().__init__(id="results_loop")
        self.mcp = mcp
        self.base_dir = base_dir

    @handler
    async def on_analysis_complete(
        self,
        result: AnalysisResult,
        ctx: WorkflowContext[None],
    ) -> None:
        """After default post-processing: show results + script, start interactive loop."""
        run_dir = result.run_dir
        plan_data = ctx.get_state("plan") or {}
        script_path = result.script_path or os.path.join(run_dir, "postprocess.sh")
        ctx.set_state("script_path", script_path)

        # Read the current script
        script_text = ""
        if os.path.exists(script_path):
            with open(script_path, encoding="utf-8") as f:
                script_text = f.read()

        # Build results summary
        summary_parts = [
            "=" * 64,
            "  SIMULATION RESULTS",
            "=" * 64,
            "",
            result.message,
            "",
            "Post-processing script:",
            f"  {script_path}",
            "",
        ]
        if result.output_files:
            summary_parts.append("Generated files:")
            for f in result.output_files[:20]:
                summary_parts.append(f"  - {f}")
            if len(result.output_files) > 20:
                summary_parts.append(f"  ... and {len(result.output_files) - 20} more")
        summary_parts += [
            "",
            "=" * 64,
            "Request changes to the post-processing script, run analysis,",
            "ask questions, or type 'done' to finish:",
        ]

        # Initialize conversation history
        existing_files = _list_output_files(run_dir)
        system_prompt = _build_system_prompt(
            plan_data, run_dir, script_path, script_text, existing_files,
        )
        ctx.set_state("results_loop_history", [
            {"role": "system", "content": system_prompt},
        ])

        await ctx.request_info(
            request_data=ResultsLoopRequest(summary="\n".join(summary_parts)),
            response_type=str,
        )

    @response_handler
    async def on_user_reply(
        self,
        request: ResultsLoopRequest,
        feedback: str,
        ctx: WorkflowContext[None],
    ) -> None:
        """Process user reply through the LLM tool-use loop."""
        history = ctx.get_state("results_loop_history") or []
        run_dir = ctx.get_state("run_dir")
        plan_data = ctx.get_state("plan") or {}
        script_path = ctx.get_state("script_path")

        # Check if we're resuming after a manual edit pause
        pending_manual_edit = ctx.get_state("pending_manual_edit_results")
        if pending_manual_edit:
            ctx.set_state("pending_manual_edit_results", False)
            result_text = await self._run_script(script_path, run_dir)
            history.append({
                "role": "tool",
                "tool_call_id": pending_manual_edit,
                "content": f"Manual edit complete. Script re-executed.\n{result_text}",
            })
        else:
            history.append({"role": "user", "content": feedback or "done"})

        client = AsyncOpenAI()
        analysis_dir = f"{run_dir}/out/analysis"
        os.makedirs(analysis_dir, exist_ok=True)

        while True:
            response = await client.chat.completions.create(
                model=os.getenv("ANALYSIS_MODEL", "gpt-4o"),
                temperature=0,
                messages=history,
                tools=_TOOLS,
            )

            choice = response.choices[0]
            msg = choice.message

            history.append(msg.model_dump(exclude_none=True))

            if not msg.tool_calls:
                text = msg.content or ""
                ctx.set_state("results_loop_history", history)
                await ctx.request_info(
                    request_data=ResultsLoopRequest(summary=text),
                    response_type=str,
                )
                return

            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)

                if fn_name == "done":
                    ctx.set_state("results_loop_history", history)
                    await ctx.yield_output({
                        "status": "complete",
                        "run_dir": run_dir,
                        "script_path": script_path,
                        "params": plan_data.get("params"),
                        "probe_points": plan_data.get("probe_points"),
                    })
                    return

                elif fn_name == "patch_and_rerun":
                    changes = fn_args["changes"]
                    try:
                        result_text = await self._patch_and_rerun(
                            changes, plan_data, run_dir, script_path, ctx,
                        )
                        history.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result_text,
                        })
                    except Exception as exc:
                        logger.exception("patch_and_rerun failed")
                        history.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"Error: {exc}",
                        })

                elif fn_name == "run_python_analysis":
                    code = fn_args["code"]
                    desc = fn_args.get("description", "Python analysis")
                    print(f"\n>>> Python: {desc}\n```python\n{code}\n```\n", flush=True)
                    logger.info(">>> results_loop python: %s", desc)
                    try:
                        r = await self.mcp.call_tool(
                            "run_analysis",
                            python_code=code,
                            work_dir=analysis_dir,
                        )
                        result = json.loads(r) if isinstance(r, str) else r
                        if result.get("returncode", -1) != 0:
                            err = result.get("stderr") or result.get("stdout") or "unknown error"
                            tool_result = f"FAILED: {err[:500]}"
                        else:
                            stdout = result.get("stdout", "").strip()
                            files = result.get("output_files", [])
                            parts = ["OK"]
                            if files:
                                parts.append("Generated: " + ", ".join(
                                    os.path.basename(f) for f in files
                                ))
                            if stdout:
                                parts.append(f"Output:\n{stdout}")
                            tool_result = "\n".join(parts)
                    except Exception as exc:
                        tool_result = f"Error: {exc}"

                    history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    })

                elif fn_name == "manual_edit":
                    ctx.set_state("results_loop_history", history)
                    ctx.set_state("pending_manual_edit_results", tc.id)
                    await ctx.request_info(
                        request_data=ResultsLoopRequest(
                            summary=(
                                f"Edit the post-processing script at:\n  {script_path}\n\n"
                                "Type 'done' when finished editing."
                            ),
                        ),
                        response_type=str,
                    )
                    return

                elif fn_name == "answer_question":
                    question = fn_args["question"]
                    from agents.utils.intent import answer_question as qa
                    plan_context = json.dumps(plan_data, indent=2)
                    answer = await qa(question, plan_context)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": answer,
                    })

            ctx.set_state("results_loop_history", history)

    async def _patch_and_rerun(
        self,
        changes: str,
        plan_data: dict,
        run_dir: str,
        script_path: str,
        ctx: WorkflowContext,
    ) -> str:
        """LLM patches the script, then re-parse and re-execute."""
        with open(script_path, encoding="utf-8") as f:
            current_script = f.read()

        new_script = await generate_script_patch(current_script, plan_data, changes)

        # Write updated script
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(new_script)
        logger.info("Script patched: %s", script_path)

        # Update system prompt with new script content
        history = ctx.get_state("results_loop_history") or []
        if history and history[0]["role"] == "system":
            existing_files = _list_output_files(run_dir)
            history[0]["content"] = _build_system_prompt(
                plan_data, run_dir, script_path, new_script, existing_files,
            )
            ctx.set_state("results_loop_history", history)

        # Re-execute
        return await self._run_script(script_path, run_dir)

    async def _run_script(self, script_path: str, run_dir: str) -> str:
        """Parse and execute the script, return a summary."""
        with open(script_path, encoding="utf-8") as f:
            script_text = f.read()

        commands = parse_script(script_text)
        results: list[str] = []

        for cmd in commands:
            logger.info(">>> %s %s", cmd.tool_name, " ".join(cmd.args))
            try:
                r = await self.mcp.call_tool(
                    "run_postprocess",
                    postprocess_tool=cmd.tool_name,
                    cwd=run_dir,
                    args=cmd.args,
                )
                result = json.loads(r) if isinstance(r, str) else r
                if result.get("returncode", -1) != 0:
                    err = result.get("stderr") or result.get("stdout") or "unknown"
                    results.append(f"FAIL {cmd.tool_name}: {err[:200]}")
                else:
                    files = result.get("output_files", [])
                    results.append(
                        f"OK {cmd.tool_name}: {len(files)} files"
                        + (f" ({', '.join(os.path.basename(f) for f in files[:5])})" if files else "")
                    )
            except Exception as exc:
                results.append(f"ERROR {cmd.tool_name}: {exc}")

        return "Script execution results:\n" + "\n".join(f"  - {r}" for r in results)
