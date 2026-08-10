"""Simulation driver — HITL event loop for the 3-executor workflow."""

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
    Content,
    WorkflowEvent,
    WorkflowRunResult,
    WorkflowRunState,
)
from agent_framework._types import ResponseStream

from agents.schemas import SetupReviewRequest, ResultsLoopRequest
from agents.simulation_agent import make_mcp_tool, make_simulation_agent
from agents.workflow import build_workflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
# Keep agent_framework at WARNING to suppress per-token streaming noise
logging.getLogger("agent_framework").setLevel(logging.WARNING)
# …but let skills discovery & load/read_skill_resource calls through
logging.getLogger("agent_framework._skills").setLevel(logging.INFO)
logger = logging.getLogger("dualsphysics_main")

BASE = str(Path(__file__).resolve().parent)

DEFAULT_SCENARIO = (
    "Simulate a moderately dense debris flow: shear-thinning non-Newtonian material "
    "with a yield stress. The initial fluid column is 0.8 m wide and 1.0 m tall in a "
    "4 m long channel. Density is around 1500 kg/m3. Run for 2 seconds with output "
    "every 0.1 s."
)


async def process_events(
    stream: ResponseStream[WorkflowEvent, WorkflowRunResult],
) -> dict[str, Any] | None:
    """Iterate workflow events, print progress, and collect HITL responses.

    Returns a responses dict if the workflow paused for request_info,
    or None if the workflow completed.
    """
    pending_requests: dict[str, Any] = {}

    def _is_function_approval_request(data: Any) -> bool:
        data_type = getattr(data, "type", None)
        type_value = getattr(data_type, "value", data_type)
        return isinstance(data, Content) and type_value == "function_approval_request"

    async for event in stream:
        if event.type == "request_info":
            req_data = event.data
            request_id = event.request_id

            if _is_function_approval_request(req_data):
                fn = getattr(req_data, "function_call", None)
                fn_name = getattr(fn, "name", "unknown_function")
                print(f"\n[Tool approval requested]: {fn_name}", flush=True)
            elif isinstance(req_data, (SetupReviewRequest, ResultsLoopRequest)):
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

            if _is_function_approval_request(req_data):
                approved = response.lower() in {"y", "yes", "approve", "approved", "ok", "true", "1", ""}
                pending_requests[request_id] = Content.from_function_approval_response(
                    approved=approved,
                    id=req_data.id,
                    function_call=req_data.function_call,
                )
            else:
                pending_requests[request_id] = response

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


async def main() -> None:
    mcp = make_mcp_tool()
    agent = make_simulation_agent()
    agent_executor = AgentExecutor(agent)

    workflow = build_workflow(mcp=mcp, agent_executor=agent_executor, base_dir=BASE)

    print("Enter your simulation scenario (press Enter for default):")
    scenario = input("> ").strip() or DEFAULT_SCENARIO

    async with mcp:
        # Initial run with scenario
        stream = workflow.run(scenario, stream=True)
        responses = await process_events(stream)

        # HITL loop: keep resuming until workflow completes
        while responses is not None:
            stream = workflow.run(responses=responses, stream=True)
            responses = await process_events(stream)


if __name__ == "__main__":
    asyncio.run(main())
