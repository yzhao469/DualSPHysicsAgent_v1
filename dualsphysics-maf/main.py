"""Agent 1 test driver — runs a full DebrisFlow2D simulation end-to-end."""
import asyncio
import json

from agents.simulation_agent import make_mcp_tool, make_simulation_agent

INITIAL_PARAMS = dict(
    dp=0.015,
    Visco=0.1,
    DensityDT=3,
    DensityDTvalue=0.1,
    coefh=0.91924,
    cflnumber=0.1,
    TimeMax=0.5,   # short run for smoke test (5 output steps instead of 50)
    TimeOut=0.1,
)


async def main() -> None:
    mcp = make_mcp_tool()
    agent = make_simulation_agent()

    async with mcp:
        result = await agent.run(
            f"Run simulation with params: {json.dumps(INITIAL_PARAMS, indent=2)}",
            tools=[mcp],
        )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
