"""Post-processing shell script utilities — generate, parse, and patch.

The shell script is the shared artifact for the post-processing phase,
analogous to Case_Def.xml for pre-processing. It is a real standalone .sh
that users can run independently, but the executor parses it into individual
commands and runs them via MCP for structured feedback.
"""

import json
import logging
import os
import re
from dataclasses import dataclass

from openai import AsyncOpenAI

from agents.utils.skill_loader import get_postprocess_skill_content

logger = logging.getLogger(__name__)

# Map binary basenames (lowercase, without platform suffix) to MCP tool names
_BINARY_TO_TOOL = {
    "partvtk": "partvtk",
    "partvtkout": "partvtkout",
    "isosurface": "isosurface",
    "computeforces": "computeforces",
    "flowtool": "flowtool",
    "boundaryvtk": "boundaryvtk",
    "floatinginfo": "floatinginfo",
}

# Lines that are shell boilerplate, not post-processing commands
_BOILERPLATE_RE = re.compile(
    r"^\s*(?:#.*|set\s|export\s|cd\s|mkdir\s|SCRIPT_DIR=|BIN_DIR=|LD_LIBRARY_PATH=|\s*$)"
)


@dataclass
class ScriptCommand:
    """A single parsed post-processing command from the shell script."""

    tool_name: str  # MCP tool name (e.g. "partvtk")
    args: list[str]  # CLI arguments
    comment: str  # Preceding comment line(s), if any


def generate_script(plan_data: dict, run_dir: str, bin_dir: str) -> str:
    """Generate a default postprocess.sh from the simulation plan.

    The script uses $SCRIPT_DIR for relocatability and is immediately
    executable as a standalone shell script.
    """
    lines = [
        "#!/bin/bash",
        "# Post-processing script for DualSPHysics simulation",
        "# Auto-generated — edit freely, then re-run.",
        "set -e",
        "",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        f'BIN_DIR="{bin_dir}"',
        'export LD_LIBRARY_PATH="$BIN_DIR:$LD_LIBRARY_PATH"',
        "",
        "# --- Fluid particles → VTK ---",
        '"$BIN_DIR"/PartVTK_linux64 '
        "-dirin \"$SCRIPT_DIR\"/out/data "
        "-savevtk \"$SCRIPT_DIR\"/out/particles/PartFluid "
        "-onlytype:-all,+fluid "
        "-vars:+idp,+vel,+rhop,+press",
        "",
        "# --- Boundary particles → VTK ---",
        '"$BIN_DIR"/PartVTK_linux64 '
        "-dirin \"$SCRIPT_DIR\"/out/data "
        "-savevtk \"$SCRIPT_DIR\"/out/particles/PartBound "
        "-onlytype:-all,+bound "
        "-vars:+mk,+rhop",
    ]

    lines.append("")  # trailing newline
    return "\n".join(lines)


def parse_script(script_text: str) -> list[ScriptCommand]:
    """Parse a postprocess.sh into individual commands.

    Recognises DualSPHysics binary calls and maps them back to MCP tool
    names.  Shell boilerplate (set -e, exports, variable assignments,
    comments-only lines, blank lines) is skipped.
    """
    commands: list[ScriptCommand] = []
    pending_comments: list[str] = []

    for raw_line in script_text.splitlines():
        line = raw_line.strip()

        # Collect comment lines as context for the next command
        if line.startswith("#") and not line.startswith("#!"):
            pending_comments.append(line)
            continue

        # Skip boilerplate
        if _BOILERPLATE_RE.match(line):
            if not line:
                pending_comments.clear()
            continue

        # Try to match a binary call
        tool_name = _match_tool(line)
        if tool_name is None:
            pending_comments.clear()
            continue

        args = _extract_args(line)
        commands.append(ScriptCommand(
            tool_name=tool_name,
            args=args,
            comment="\n".join(pending_comments),
        ))
        pending_comments = []

    return commands


def _match_tool(line: str) -> str | None:
    """Return the MCP tool name if the line invokes a known binary."""
    # Handle quoted $BIN_DIR paths and direct paths
    # e.g. "$BIN_DIR"/PartVTK_linux64 or /abs/path/PartVTK_linux64
    for key in _BINARY_TO_TOOL:
        # Case-insensitive match on the binary name portion
        if re.search(rf"\b{key}[\w]*", line, re.IGNORECASE):
            return _BINARY_TO_TOOL[key]
    return None


def _extract_args(line: str) -> list[str]:
    """Extract CLI arguments from a command line, dropping the binary path."""
    # Remove the binary portion (everything up to and including the binary name)
    # Pattern: optional quotes/"$BIN_DIR"/ then BinaryName_linux64
    cleaned = re.sub(
        r'^.*?(?:"\$BIN_DIR"/|/\S+/)\S+_linux64\s*',
        "",
        line,
    )
    # Expand $SCRIPT_DIR references to relative paths for MCP calls
    cleaned = re.sub(r'"\$SCRIPT_DIR"/', "", cleaned)
    cleaned = re.sub(r"\$SCRIPT_DIR/", "", cleaned)
    # Split on whitespace, respecting simple quoting
    return cleaned.split()


PATCH_SCRIPT_SYSTEM_PROMPT = """\
You are an expert DualSPHysics post-processing engineer. You will be given:
1. The current postprocess.sh script.
2. The simulation plan (params).
3. A user instruction describing what to change.

Return the COMPLETE updated shell script. Keep the same structure:
- Shebang, set -e, SCRIPT_DIR/BIN_DIR/LD_LIBRARY_PATH setup
- One command per line with a comment above each section
- Use "$BIN_DIR"/ prefix for binaries, "$SCRIPT_DIR"/ prefix for data paths

Only add, remove, or modify post-processing commands as requested.
Return the raw script only, no markdown fences.
"""


async def generate_script_patch(
    current_script: str,
    plan_data: dict,
    user_request: str,
) -> str:
    """Call LLM to produce an updated postprocess.sh based on user request."""
    skill_text = get_postprocess_skill_content()

    user_content = (
        f"### Current postprocess.sh\n```bash\n{current_script}\n```\n\n"
        f"### Simulation Plan\n```json\n{json.dumps(plan_data, indent=2)}\n```\n\n"
        f"### Post-Processing Reference\n{skill_text}\n\n"
        f"### User Instruction\n{user_request}"
    )

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=os.getenv("PATCH_MODEL", "gpt-4o"),
        temperature=0,
        messages=[
            {"role": "system", "content": PATCH_SCRIPT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    return response.choices[0].message.content or current_script
