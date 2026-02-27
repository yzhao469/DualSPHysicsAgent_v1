"""Smoke test driver — passes explicit numeric parameters, bypasses agent reasoning.

Use this to verify the simulation pipeline without LLM parameter reasoning.
Note: the agent will still call request_user_review for confirmation.
"""
import asyncio
import json

from agents.simulation_agent import make_mcp_tool, make_simulation_agent, get_agent_tools

EXPLICIT_PARAMS = dict(
    dp=0.015,
    rhop0=1200,
    phase_rhop=1200,
    visco_nn=0.1,
    tau_yield=0.005,
    HBP_m=10,
    HBP_n=1.2,
    Visco=0.1,
    DensityDT=3,
    DensityDTvalue=0.1,
    coefh=0.91924,
    cflnumber=0.1,
    TimeMax=0.5,
    TimeOut=0.1,
)


async def main() -> None:
    mcp = make_mcp_tool()
    agent = make_simulation_agent()

    async with mcp:
        result = await agent.run(
            f"Run simulation with these exact parameters (skip Phase 1 reasoning, "
            f"use these values directly):\n{json.dumps(EXPLICIT_PARAMS, indent=2)}",
            tools=get_agent_tools(mcp),
        )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
