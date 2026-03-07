"""ResultsLoopExecutor — LLM tool-use interactive post-processing loop.

Replaces the old ReviewExecutor (results phase) and AnalyzeExecutor
analysis mode. Uses OpenAI function calling so the LLM can chain
post-processing tools and Python analysis in a single turn, with
full conversation memory.
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
from agents.utils.skill_loader import get_postprocess_skill_content

logger = logging.getLogger(__name__)

# OpenAI function definitions for the results loop LLM
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_postprocess",
            "description": (
                "Run a DualSPHysics post-processing tool (partvtk, partvtkout, "
                "isosurface, computeforces, flowtool, boundaryvtk, floatinginfo, "
                "measuretool). All paths in args must be relative to the run directory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the post-processing tool.",
                        "enum": [
                            "partvtk", "partvtkout", "isosurface",
                            "computeforces", "flowtool", "boundaryvtk",
                            "floatinginfo", "measuretool",
                        ],
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Command-line arguments for the tool.",
                    },
                },
                "required": ["tool_name", "args"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python_analysis",
            "description": (
                "Execute a Python script for data analysis (CSV parsing, "
                "computing derived quantities, plotting with matplotlib). "
                "The script runs with out/analysis/ as its working directory. "
                "Use relative paths: ../data/, ../particles/, ../measuretool/ "
                "to access other output directories."
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
            "name": "answer_question",
            "description": (
                "Answer a conceptual question about the simulation results, "
                "DualSPHysics, physics, or post-processing techniques. "
                "For questions that require reading data files, use "
                "run_postprocess or run_python_analysis instead."
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


def _build_system_prompt(plan_data: dict, run_dir: str, existing_files: list[str]) -> str:
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
        f"### Post-Processing Reference\n{skill_text}\n\n"
        "### Your Role\n"
        "- Use `run_postprocess` for PartVTK, IsoSurface, ComputeForces, etc.\n"
        "- Use `run_python_analysis` for CSV parsing, computing metrics, and plotting.\n"
        "- You can chain multiple tool calls in one turn.\n"
        "- ALL paths in postprocess args must be relative to the run directory.\n"
        "- Python scripts run with out/analysis/ as cwd. Use relative paths.\n"
        "- PartVTK CSV uses semicolon separator. Use numpy.genfromtxt with delimiter=';'.\n"
        "- PartVTK CSV columns: Idp;Pos.x;Pos.y;Pos.z;Vel.x;Vel.y;Vel.z;Rhop "
        "(when vars include idp,vel,rhop).\n"
        "- In Python, use matplotlib with Agg backend for plots.\n"
        "- When the user is done (says 'done', 'exit', 'finished', etc.), call `done`.\n"
        "- When the user gives short affirmative responses like 'done', 'that is all', "
        "'finished', 'exit', or 'no more', call `done`.\n"
    )


def _list_output_files(run_dir: str) -> list[str]:
    """List existing output files in the run directory."""
    import os

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
        """After default post-processing: show results, start interactive loop."""
        run_dir = result.run_dir
        plan_data = ctx.get_state("plan") or {}

        # Build results summary
        summary_parts = [
            "=" * 64,
            "  SIMULATION RESULTS",
            "=" * 64,
            "",
            result.message,
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
            "Request analysis, ask questions, or type 'done' to finish:",
        ]

        # Initialize conversation history
        existing_files = _list_output_files(run_dir)
        system_prompt = _build_system_prompt(plan_data, run_dir, existing_files)
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

        # Append user message
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

            # Append assistant message to history
            history.append(msg.model_dump(exclude_none=True))

            if not msg.tool_calls:
                # Text response — show to user and loop
                text = msg.content or ""
                ctx.set_state("results_loop_history", history)
                await ctx.request_info(
                    request_data=ResultsLoopRequest(summary=text),
                    response_type=str,
                )
                return

            # Process tool calls
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)

                if fn_name == "done":
                    ctx.set_state("results_loop_history", history)
                    await ctx.yield_output({
                        "status": "complete",
                        "run_dir": run_dir,
                        "params": plan_data.get("params"),
                        "probe_points": plan_data.get("probe_points"),
                    })
                    return

                elif fn_name == "run_postprocess":
                    tool_name = fn_args["tool_name"]
                    args = fn_args["args"]
                    logger.info(">>> results_loop postprocess: %s %s", tool_name, args)
                    try:
                        r = await self.mcp.call_tool(
                            "run_postprocess",
                            postprocess_tool=tool_name,
                            args=args,
                            cwd=run_dir,
                        )
                        result = json.loads(r) if isinstance(r, str) else r
                        if result.get("returncode", -1) != 0:
                            err = result.get("stderr") or result.get("stdout") or "unknown error"
                            tool_result = f"FAILED (rc={result.get('returncode')}): {err[:500]}"
                        else:
                            files = result.get("output_files", [])
                            tool_result = f"OK — {len(files)} output files"
                            if files:
                                tool_result += ": " + ", ".join(
                                    os.path.basename(f) for f in files[:10]
                                )
                    except Exception as exc:
                        tool_result = f"Error: {exc}"

                    history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
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

                elif fn_name == "answer_question":
                    question = fn_args["question"]
                    # Use the skill content + plan as context
                    from agents.utils.intent import answer_question as qa
                    plan_context = json.dumps(plan_data, indent=2)
                    answer = await qa(question, plan_context)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": answer,
                    })

            # Continue loop — LLM may chain more tool calls or produce text
            ctx.set_state("results_loop_history", history)
