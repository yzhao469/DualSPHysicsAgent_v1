"""Setup review constants and helpers.

Contains tool definitions, Chat Completions history helpers, instruction
builder, plan summary formatter, and datalake file utilities used by
PlanAndBuildExecutor's setup review HITL loop.
"""

import json
from pathlib import Path

from agents.schemas import SimulationPlan

MAX_BUILD_RECOVERY_ATTEMPTS = 3

# ─────────────────────────────────────────────────────────────────────────────
# OpenAI function definitions for the setup review LLM (Chat Completions API)
# ─────────────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "patch_and_rebuild",
            "description": (
                "Apply changes to the simulation case XML based on the user's "
                "description. Re-runs GenCase and regenerates the visualization."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "changes": {
                        "type": "string",
                        "description": "Description of what to change in the simulation setup.",
                    },
                },
                "required": ["changes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "answer_question",
            "description": (
                "Answer a question about the simulation plan, physics, "
                "DualSPHysics, or the current setup."
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
            "name": "approve",
            "description": "User is satisfied with the setup. Proceed to simulation.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manual_edit",
            "description": (
                "Let the user manually edit the Case_Def.xml file directly. "
                "Use this when the user says they want to edit the file themselves."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_reference",
            "description": (
                "Fetch detailed reference for a specific XML/geometry topic. "
                "Use this when you need exact syntax, drawing primitives, "
                "transform rules, or composition examples."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": [
                            "xml-overview",
                            "drawing-shapes",
                            "fill-and-modification",
                            "transforms-and-variables",
                            "composition-patterns",
                        ],
                        "description": "Which reference to fetch.",
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replan",
            "description": (
                "Scrap the current plan and start over with a different scenario."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "new_scenario": {
                        "type": "string",
                        "description": "The new scenario description.",
                    },
                },
                "required": ["new_scenario"],
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Datalake file utilities
# ─────────────────────────────────────────────────────────────────────────────

_DATALAKE_EXTENSIONS = {".xml", ".png", ".jpg", ".jpeg", ".stl", ".vtk", ".ply", ".csv"}
_MESH_EXTENSIONS = {".stl", ".vtk", ".ply", ".csv"}


def list_datalake_files(base_dir: str) -> list[str]:
    """Return relative paths of all XML and image files in the datalake directory."""
    datalake = Path(base_dir) / "datalake"
    if not datalake.is_dir():
        return []
    return sorted(
        str(p.relative_to(base_dir))
        for p in datalake.rglob("*")
        if p.suffix.lower() in _DATALAKE_EXTENSIONS
    )


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in {".png", ".jpg", ".jpeg"}


def is_mesh_file(path: Path) -> bool:
    return path.suffix.lower() in _MESH_EXTENSIONS


# ─────────────────────────────────────────────────────────────────────────────
# Instructions and plan formatting
# ─────────────────────────────────────────────────────────────────────────────


def build_instructions(
    plan_data: dict,
    run_dir: str,
    build_error: str | None = None,
    retry_count: int = 0,
    max_retry_count: int = MAX_BUILD_RECOVERY_ATTEMPTS,
) -> str:
    """Build the instructions for the setup review LLM."""
    plan_summary = json.dumps(plan_data, indent=2)
    build_status = (
        "Build failed before review started."
        if build_error
        else "Build completed successfully."
    )
    failure_guidance = ""
    if build_error:
        failure_guidance = (
            f"### Current Build Error\n{build_error}\n\n"
            f"### Recovery Attempts\n{retry_count} of {max_retry_count}\n\n"
        )
    return (
        "You are a helpful assistant reviewing a DualSPHysics simulation setup. "
        "The user has been shown the simulation plan and a visualization "
        "of the particle geometry.\n\n"
        f"### Build Status\n{build_status}\n\n"
        f"{failure_guidance}"
        f"### Current Simulation Plan\n```json\n{plan_summary}\n```\n\n"
        f"### Run Directory\n{run_dir}\n\n"
        "### Your Role\n"
        "- If the build status is failed, do not call `approve` until the setup has been rebuilt successfully.\n"
        "- If the user is happy with the setup, call `approve` to proceed to simulation.\n"
        "- If the user wants changes (geometry, parameters, probes), call `patch_and_rebuild`.\n"
        "- If the user wants to edit the XML file themselves, call `manual_edit`.\n"
        "- If the user asks a question, call `answer_question`.\n"
        "- If the user wants to start over entirely, call `replan`.\n"
        f"- If recovery keeps failing and you have already used {max_retry_count} rebuild attempts, call `replan`.\n"
        "- Always be concise and helpful.\n"
        "- When the user gives short affirmative responses like 'yes', 'ok', 'looks good', "
        "'go ahead', 'proceed', or just presses Enter, call `approve`.\n"
    )


def format_plan_summary(plan: SimulationPlan) -> str:
    """Build a human-readable summary of the simulation plan."""
    lines = [
        "=" * 64,
        "  SIMULATION PLAN",
        "=" * 64,
        "",
        "### Reasoning",
        plan.reasoning,
        "",
    ]
    if plan.geometry_xml:
        lines += [
            "### Geometry XML",
            "```xml",
            plan.geometry_xml,
            "```",
            "",
        ]
    lines.append("### Physics Parameters")
    for field, value in plan.params.model_dump().items():
        lines.append(f"  {field:20s} = {value}")
    lines += [
        "",
        "=" * 64,
        "A visualization of the particle configuration has been generated.",
        "Approve, request changes, or ask a question:",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Chat Completions API history helpers
# ─────────────────────────────────────────────────────────────────────────────


def system_message(text: str) -> dict:
    """Build a Chat Completions system message."""
    return {"role": "system", "content": text}


def user_message(text: str) -> dict:
    """Build a Chat Completions user message."""
    return {"role": "user", "content": text}


def user_message_with_images(text: str, images: list[tuple[str, str]]) -> dict:
    """Build a Chat Completions user message with text + one or more images.

    Args:
        text: The text content.
        images: List of (base64_data, media_type) tuples.
    """
    content: list[dict] = [{"type": "text", "text": text}]
    for img_b64, media_type in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{img_b64}"},
        })
    return {"role": "user", "content": content}


def assistant_message(text: str) -> dict:
    """Build a Chat Completions assistant message."""
    return {"role": "assistant", "content": text}


def tool_result(tool_call_id: str, output: str) -> dict:
    """Build a Chat Completions tool result message."""
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": output,
    }
