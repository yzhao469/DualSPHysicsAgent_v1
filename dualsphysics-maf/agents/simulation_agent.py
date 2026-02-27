"""Agent 1 — SimulationRunner: interprets natural language scenario descriptions
and drives a full DebrisFlow2D simulation end-to-end with human-in-the-loop review."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from agent_framework import Agent, MCPStdioTool
from agent_framework.anthropic import AnthropicClient

from agents.tools.user_review import request_user_review
from agents.tools.visualize_geometry import visualize_geometry

BASE = "/home/danrong/projects/DualSPHysics_NN_v5.0.1/dualsphysics-maf"

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
    """Create Agent 1 (SimulationRunner) with two-phase reasoning instructions."""
    skill_content = _SKILL_FILE.read_text(encoding="utf-8")
    template = _jinja_env.get_template("simulation_agent.j2")
    instructions = template.render(base=BASE, skill_content=skill_content)

    return Agent(
        client=AnthropicClient(model_id="claude-sonnet-4-6"),
        name="SimulationRunner",
        instructions=instructions,
    )


def get_agent_tools(mcp: MCPStdioTool) -> list:
    """Return the full tool list: MCP tools + Python callable HITL tools."""
    return [mcp, request_user_review, visualize_geometry]
