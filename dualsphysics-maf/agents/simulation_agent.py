"""Agent 1 — SimulationPlanner: reasons about physics and geometry from a
natural-language scenario description.  Returns structured SimulationPlan JSON.

The agent has NO tools — it only reasons.  All tool orchestration is handled
by SimulationCoordinator (see coordinator.py).

Uses OpenAI GPT-4o for native structured output (response_format)."""

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from agent_framework import Agent, MCPStdioTool
from agent_framework.openai import OpenAIChatClient

from agents.schemas import SimulationPlan

BASE = str(Path(__file__).resolve().parents[1])

_PROMPTS_DIR = Path(BASE) / "agents/prompts"
_SKILL_FILE = Path(BASE) / "skills/dualsphysics_xml_guide.md"

_jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), keep_trailing_newline=True)


def make_mcp_tool() -> MCPStdioTool:
    """Create the MCP stdio tool pointing at our DualSPHysics server."""
    return MCPStdioTool(
        name="dualsphysics",
        command=f"{BASE}/.venv/bin/python",
        args=[f"{BASE}/mcp_server/server.py"],
        cwd=BASE,
    )


def make_simulation_agent() -> Agent:
    """Create the SimulationPlanner agent with structured output.

    The agent receives a scenario description, reasons about geometry and
    physics, and returns a SimulationPlan JSON via OpenAI structured output.
    It has no tools — only reasoning capability.
    """
    skill_content = _SKILL_FILE.read_text(encoding="utf-8")
    template = _jinja_env.get_template("simulation_agent.j2")
    instructions = template.render(base=BASE, skill_content=skill_content)

    client = OpenAIChatClient(model_id=os.getenv("PLANNER_MODEL", "gpt-4o"))

    return Agent(
        client=client,
        name="SimulationPlanner",
        instructions=instructions,
        default_options={"response_format": SimulationPlan},
    )
