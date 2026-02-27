"""Agent 1 test driver — runs a full DebrisFlow2D simulation end-to-end.

Pass a natural language scenario description and the agent will:
  1. Reason about appropriate physical parameters  (Phase 1)
  2. Present them for user review + optional 3D viz  (Phase 2 — HITL)
  3. Run the full simulation pipeline                (Phase 3)
  4. Return a JSON summary with results

For a quick smoke test with explicit numeric parameters, see main_smoke.py.
"""
import asyncio

from agents.simulation_agent import make_mcp_tool, make_simulation_agent, get_agent_tools

SCENARIO = (
    "Simulate a moderately dense debris flow: shear-thinning non-Newtonian material "
    "with a yield stress. The initial fluid column is 0.8 m wide and 1.0 m tall in a "
    "4 m long channel. Density is around 1500 kg/m3. Run for 2 seconds with output "
    "every 0.1 s."
)


async def main() -> None:
    mcp = make_mcp_tool()
    agent = make_simulation_agent()

    async with mcp:
        result = await agent.run(SCENARIO, tools=get_agent_tools(mcp))
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
