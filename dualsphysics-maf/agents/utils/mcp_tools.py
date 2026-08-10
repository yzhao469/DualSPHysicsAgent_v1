"""MCP tool response validation and error diagnostics.

Provides a unified check for MCP tool responses (JSON or plain text)
and pattern-based diagnostic hints for build and simulation failures.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _to_json_dict(value: Any) -> dict[str, Any] | None:
    """Best-effort conversion of *value* into a JSON dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def parse_mcp_tool_result(response: Any) -> dict[str, Any] | None:
    """Extract structured MCP tool result dict from mixed response formats.

    Newer framework versions may return lists of Content objects rather than
    raw JSON strings/dicts. This helper walks common wrappers and returns the
    first dict-like payload it can decode.
    """
    queue: list[Any] = [response]

    while queue:
        current = queue.pop(0)

        # Direct dict / JSON string
        parsed = _to_json_dict(current)
        if parsed is not None:
            return parsed

        # Sequence of content fragments
        if isinstance(current, (list, tuple)):
            queue.extend(current)
            continue

        # Content-like object fields that may carry payloads
        for attr in ("result", "output", "text", "message"):
            value = getattr(current, attr, None)
            if value is not None:
                parsed = _to_json_dict(value)
                if parsed is not None:
                    return parsed
                if isinstance(value, (list, tuple, dict)):
                    queue.append(value)

        # Pydantic-like model dump as a fallback
        model_dump = getattr(current, "model_dump", None)
        if callable(model_dump):
            try:
                dumped = model_dump(exclude_none=True)
            except TypeError:
                dumped = model_dump()
            if isinstance(dumped, dict):
                if "returncode" in dumped:
                    return dumped
                queue.extend(v for v in dumped.values() if isinstance(v, (dict, list, tuple, str)))

    return None


def mcp_tool_result_text(response: Any) -> str:
    """Return a readable text representation for logging/errors."""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return json.dumps(response)
    if isinstance(response, (list, tuple)):
        parts = [mcp_tool_result_text(item) for item in response]
        return "\n".join(p for p in parts if p)

    for attr in ("text", "message", "stderr", "stdout"):
        value = getattr(response, attr, None)
        if isinstance(value, str) and value:
            return value

    return str(response)


def check_mcp_tool_result(tool_name: str, response: Any) -> None:
    """Validate MCP tool response; raise RuntimeError with details on failure.

    Handles both structured JSON responses (with returncode/stderr) and
    plain-text error responses (starting with 'ERROR').
    """
    # Try to parse as structured JSON/result dict
    result = parse_mcp_tool_result(response)

    if isinstance(result, dict):
        if result.get("returncode", 0) != 0:
            error_detail = result.get("stderr") or result.get("stdout") or str(response)
            raise RuntimeError(f"{tool_name} failed: {error_detail}")
        return

    # Fall back to plain-text error detection
    response_text = mcp_tool_result_text(response).strip()
    if response_text.startswith("ERROR"):
        raise RuntimeError(f"{tool_name} failed: {response_text}")


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
