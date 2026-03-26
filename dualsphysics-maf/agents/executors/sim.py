"""SimExecutor — deterministic simulation pipeline.

Reads plan + run_dir from workflow state and runs the solver.
No longer terminal — passes control to AnalyzeExecutor for post-processing.
On failure, routes back to PlanAndBuildExecutor for parameter adjustments.
"""

import json
import logging
import shutil

from agent_framework import (
    Executor,
    MCPStdioTool,
    WorkflowContext,
    handler,
)

from agents.schemas import ReviewResult

logger = logging.getLogger(__name__)

# Common DualSPHysics failure patterns and diagnostic hints.
# Patterns are checked with `in` against lowercased error text, so use
# multi-word phrases to avoid false positives (e.g. "out of memory" not "memory").
_FAILURE_DIAGNOSTICS: list[tuple[str, str]] = [
    ("cfl condition", "CFL violation — try reducing CflNumber (e.g. 0.05) or decreasing TimeOut."),
    ("particle out", "Particle explosion — check initial density (rhop0) and geometry containment."),
    ("nan detected", "NaN detected — parameters may be out of range; check viscosity, yield stress, or density."),
    ("out of memory", "Out of memory — reduce particle count by increasing dp or shrinking the domain."),
    ("diverge", "Solver divergence — try lowering TimeMax for a shorter test run first."),
]


def _has_gpu() -> bool:
    """Check whether an NVIDIA GPU is available via nvidia-smi."""
    return shutil.which("nvidia-smi") is not None


def _diagnose_failure(error_text: str) -> str:
    """Return diagnostic hints based on common failure patterns in error text."""
    error_lower = error_text.lower()
    hints = [hint for pattern, hint in _FAILURE_DIAGNOSTICS if pattern in error_lower]
    if hints:
        return "\n".join(f"  - {h}" for h in hints)
    return "  - No specific diagnostic match. Review the error output for details."


class SimExecutor(Executor):
    """Deterministic: runs the DualSPHysics solver."""

    def __init__(self, mcp: MCPStdioTool, base_dir: str) -> None:
        super().__init__(id="sim")
        self.mcp = mcp
        self.base_dir = base_dir

    @handler
    async def on_approved(
        self, trigger: ReviewResult, ctx: WorkflowContext[ReviewResult]
    ) -> None:
        """Run the solver and pass to AnalyzeExecutor, or recover on failure."""
        plan_data = ctx.get_state("plan")
        run_dir = ctx.get_state("run_dir")
        assert plan_data is not None, "No plan in workflow state"
        assert run_dir is not None, "No run_dir in workflow state"

        # Run simulation (GPU if available, else CPU)
        use_gpu = _has_gpu()
        logger.info(">>> run_simulation (gpu=%s)", use_gpu)
        try:
            r = await self.mcp.call_tool(
                "run_simulation",
                case_path=f"{run_dir}/out/Case_Def",
                output_dir=f"{run_dir}/out",
                gpu=use_gpu,
            )
            sim_result = json.loads(r) if isinstance(r, str) else r
            if sim_result.get("returncode", -1) != 0:
                error_text = sim_result.get("stderr") or sim_result.get("stdout") or str(r)
                raise RuntimeError(f"run_simulation failed:\n{error_text}")
        except RuntimeError as exc:
            logger.error("Simulation failed: %s", exc)
            error_msg = str(exc)
            diagnostics = _diagnose_failure(error_msg)

            # Route back to setup review with error context so the user can
            # adjust parameters (CFL, density, TimeMax, etc.) and retry.
            await ctx.send_message(
                ReviewResult(
                    route="full_replan",
                    feedback=(
                        f"Simulation failed with error:\n{error_msg}\n\n"
                        f"Possible causes:\n{diagnostics}\n\n"
                        "Please adjust parameters and try again."
                    ),
                )
            )
            return

        logger.info("run_simulation OK")

        # Pass to AnalyzeExecutor (default post-processing)
        await ctx.send_message(
            ReviewResult(route="sim", feedback="")
        )
