"""Agent 1 — SimulationPlanner: reasons about physics and geometry from a
natural-language scenario description.  Returns structured SimulationPlan JSON.

The agent uses SkillsProvider for progressive-disclosure of the DualSPHysics
reference material.  The LLM calls load_skill / read_skill_resource tools to
retrieve only the sections it needs, then produces a SimulationPlan JSON via
OpenAI structured output.

All tool orchestration (MCP) is handled by the executor pipeline."""

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from agent_framework import Agent, MCPStdioTool, SkillsProvider
from agent_framework.openai import OpenAIChatClient

from agents.schemas import SimulationPlan

BASE = str(Path(__file__).resolve().parents[1])

_PROMPTS_DIR = Path(BASE) / "agents/prompts"
_SKILLS_DIR = Path(BASE) / "skills"

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

    Domain knowledge is provided via SkillsProvider (progressive disclosure):
    the system prompt advertises the skill name/description (~100 tokens), and
    the agent calls load_skill + read_skill_resource to fetch only the
    reference sections it needs.
    """
    template = _jinja_env.get_template("simulation_agent.j2")
    instructions = template.render(base=BASE)

    client = OpenAIChatClient(model=os.getenv("PLANNER_MODEL", "gpt-4o"))

    # SkillsProvider registers its tools with approval_mode="always_require" by
    # default, so every load_skill / read_skill_resource call would raise a
    # function-approval request.  The workflow has exactly one intended
    # confirmation point -- the setup review before the simulation runs -- and
    # both skill dirs are read-only Markdown, so opt these two tools out.
    # run_skill_script is deliberately left requiring approval.
    skills_provider = SkillsProvider.from_paths(
        str(_SKILLS_DIR),
        disable_load_skill_approval=True,
        disable_read_skill_resource_approval=True,
    )

    return Agent(
        client=client,
        name="SimulationPlanner",
        instructions=instructions,
        default_options={"response_format": SimulationPlan},
        context_providers=[skills_provider],
    )
