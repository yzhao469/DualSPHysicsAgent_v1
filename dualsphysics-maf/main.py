"""Workflow-based simulation driver with HITL review gates.

Uses agent_framework's Workflow system:
  - SimulationCoordinator (Executor): deterministic orchestrator
  - SimulationPlanner (Agent via AgentExecutor): LLM reasoning only
  - HITL via workflow request_info / response_handler pattern
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env from the project directory (OPENAI_API_KEY, etc.)
load_dotenv(Path(__file__).resolve().parent / ".env")

from agent_framework import (
    AgentExecutor,
    WorkflowBuilder,
    WorkflowEvent,
    WorkflowRunResult,
    WorkflowRunState,
)
from agent_framework._types import ResponseStream

from agents.coordinator import SimulationCoordinator
from agents.schemas import ReviewRequest
from agents.simulation_agent import make_mcp_tool, make_simulation_agent

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
# Keep agent_framework at WARNING to suppress per-token streaming noise
logging.getLogger("agent_framework").setLevel(logging.WARNING)
logger = logging.getLogger("dualsphysics_main")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE = "/home/danrong/projects/DualSPHysics_NN_v5.0.1/dualsphysics-maf"

SCENARIO = (
    "Simulate a moderately dense debris flow: shear-thinning non-Newtonian material "
    "with a yield stress. The initial fluid column is 0.8 m wide and 1.0 m tall in a "
    "4 m long channel. Density is around 1500 kg/m3. Run for 2 seconds with output "
    "every 0.1 s."
)


# ---------------------------------------------------------------------------
# Event processing
# ---------------------------------------------------------------------------
async def process_events(
    stream: ResponseStream[WorkflowEvent, WorkflowRunResult],
) -> dict[str, Any] | None:
    """Iterate workflow events, print progress, and collect HITL responses.

    Returns a responses dict if the workflow paused for request_info,
    or None if the workflow completed.
    """
    pending_requests: dict[str, Any] = {}

    async for event in stream:
        if event.type == "request_info":
            # The request data is a ReviewRequest dataclass
            req_data = event.data
            request_id = event.request_id

            if isinstance(req_data, ReviewRequest):
                print(req_data.summary, flush=True)
            else:
                print(f"\n[Request from {event.source_executor_id}]: {req_data}", flush=True)

            # Prompt user via terminal
            loop = asyncio.get_running_loop()
            try:
                response = await loop.run_in_executor(
                    None, lambda: input("\nYour response: ").strip()
                )
            except EOFError:
                response = "yes"

            pending_requests[request_id] = response

        elif event.type == "output":
            # Only log final outputs from the coordinator (not agent streaming tokens)
            if event.executor_id == "coordinator":
                logger.info("Workflow output received")

        elif event.type == "executor_failed":
            logger.error("Executor %s failed: %s", event.executor_id, event.details)

        elif event.type == "failed":
            logger.error("Workflow failed: %s", event.details)

    # Check final state
    result = await stream.get_final_response()
    final_state = result.get_final_state()
    logger.info("Workflow state: %s", final_state)

    if final_state == WorkflowRunState.IDLE_WITH_PENDING_REQUESTS:
        return pending_requests

    # Workflow completed — print outputs
    outputs = result.get_outputs()
    if outputs:
        print("\n" + "=" * 64)
        print("  SIMULATION COMPLETE")
        print("=" * 64)
        for out in outputs:
            print(json.dumps(out, indent=2, default=str))
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    mcp = make_mcp_tool()
    agent = make_simulation_agent()
    agent_executor = AgentExecutor(agent)
    coordinator = SimulationCoordinator(mcp=mcp, base_dir=BASE)

    workflow = (
        WorkflowBuilder(start_executor=coordinator)
        .add_edge(coordinator, agent_executor)  # coordinator → agent (reasoning request)
        .add_edge(agent_executor, coordinator)  # agent → coordinator (plan response)
        .build()
    )

    async with mcp:
        # Initial run with scenario
        stream = workflow.run(SCENARIO, stream=True)
        responses = await process_events(stream)

        # HITL loop: keep resuming until workflow completes
        while responses is not None:
            stream = workflow.run(responses=responses, stream=True)
            responses = await process_events(stream)


if __name__ == "__main__":
    asyncio.run(main())
