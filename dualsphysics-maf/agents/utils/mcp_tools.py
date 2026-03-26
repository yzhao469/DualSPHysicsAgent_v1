"""MCP tool response validation and error diagnostics.

Provides a unified check for MCP tool responses (JSON or plain text)
and pattern-based diagnostic hints for build and simulation failures.
"""

import json
import logging

logger = logging.getLogger(__name__)


def check_mcp_tool_result(tool_name: str, response: str | dict) -> None:
    """Validate MCP tool response; raise RuntimeError with details on failure.

    Handles both structured JSON responses (with returncode/stderr) and
    plain-text error responses (starting with 'ERROR').
    """
    # Try to parse as structured JSON
    if isinstance(response, str):
        try:
            result = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            logger.debug("%s response is not JSON, treating as plain text", tool_name)
            result = None
    else:
        result = response

    if isinstance(result, dict):
        if result.get("returncode", 0) != 0:
            error_detail = result.get("stderr") or result.get("stdout") or str(response)
            raise RuntimeError(f"{tool_name} failed: {error_detail}")
        return

    # Fall back to plain-text error detection
    if isinstance(response, str) and response.startswith("ERROR"):
        raise RuntimeError(f"{tool_name} failed: {response}")


def diagnose_error(
    error_text: str,
    diagnostics: list[tuple[str, str]],
) -> str:
    """Return diagnostic hints based on pattern matching against error text.

    Args:
        error_text: The error output to analyze.
        diagnostics: List of (pattern, hint) tuples. Patterns are matched
            case-insensitively with ``in``.
    """
    error_lower = error_text.lower()
    hints = [hint for pattern, hint in diagnostics if pattern in error_lower]
    if hints:
        return "\n".join(f"  - {h}" for h in hints)
    return "  - No specific diagnostic match. Review the error output for details."


# Common GenCase / geometry build failure patterns.
BUILD_DIAGNOSTICS: list[tuple[str, str]] = [
    ("xml syntax", "Malformed XML — check for unclosed tags, invalid attributes, or encoding issues."),
    ("unknown element", "Unknown XML element — verify geometry element names against the DualSPHysics reference."),
    ("file not found", "File not found — a referenced mesh or input file may be missing from the run directory."),
    ("no such file", "File not found — a referenced mesh or input file may be missing from the run directory."),
    ("boundary error", "Boundary definition error — check that all boundaries are properly enclosed and non-overlapping."),
    ("particle generation", "Particle generation error — verify dp spacing and that geometry volumes are valid."),
    ("out of memory", "Out of memory during GenCase — reduce particle count by increasing dp or shrinking the domain."),
    ("permission denied", "Permission denied — check file/directory write permissions in the run directory."),
]

# Common DualSPHysics solver failure patterns.
SIM_DIAGNOSTICS: list[tuple[str, str]] = [
    ("cfl condition", "CFL violation — try reducing CflNumber (e.g. 0.05) or decreasing TimeOut."),
    ("particle out", "Particle explosion — check initial density (rhop0) and geometry containment."),
    ("nan detected", "NaN detected — parameters may be out of range; check viscosity, yield stress, or density."),
    ("out of memory", "Out of memory — reduce particle count by increasing dp or shrinking the domain."),
    ("diverge", "Solver divergence — try lowering TimeMax for a shorter test run first."),
]
