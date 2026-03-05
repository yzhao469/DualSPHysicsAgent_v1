"""PatchExecutor — LLM-driven targeted patching of an existing case.

Reads the current Case_Def.xml, sends it to the LLM with the user's
feedback, and applies only the changed parts (geometry, params, probes).
"""

import json
import logging
import os
from pathlib import Path

from openai import AsyncOpenAI

from agent_framework import (
    Executor,
    MCPStdioTool,
    WorkflowContext,
    handler,
)

from agents.utils.build_utils import rebuild_gencase_viz
from agents.schemas import BuildResult, PatchRequest

logger = logging.getLogger(__name__)

_SKILL_FILE = Path(__file__).resolve().parent.parent.parent / "skills" / "dualsphysics_xml_guide.md"

_PATCH_SYSTEM_PROMPT = """\
You are an expert DualSPHysics simulation engineer. You will be given:
1. The current Case_Def.xml for a simulation case.
2. The current simulation plan (geometry_xml, params, probe_points).
3. A user instruction describing what to change.

Return a JSON object with ONLY the keys that need to change. Possible keys:
- "geometry_xml": string — full <geometry>...</geometry> XML block (only if geometry changes)
- "params": object — only the physics parameter fields that change (partial update)
- "probe_points": array of [x, y, z] triples (only if probes change)

Do NOT include keys that don't need to change. If only density changes, return {"params": {"rhop0": 2000, "phase_rhop": 2000}}.
Return valid JSON only, no markdown fences.
"""


async def _generate_patch(
    current_xml: str,
    plan_data: dict,
    feedback: str,
) -> dict:
    """Call LLM to produce a targeted patch."""
    skill_text = ""
    if _SKILL_FILE.exists():
        skill_text = f"\n\n### Reference Material\n{_SKILL_FILE.read_text()}"

    user_content = (
        f"### Current Plan\n```json\n{json.dumps(plan_data, indent=2)}\n```\n\n"
        f"### Current Case_Def.xml\n```xml\n{current_xml}\n```\n\n"
        f"{skill_text}\n\n"
        f"### User Instruction\n{feedback}"
    )

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=os.getenv("PATCH_MODEL", "gpt-4o"),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _PATCH_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)


class PatchExecutor(Executor):
    """LLM-driven targeted patching of the current simulation case."""

    def __init__(self, mcp: MCPStdioTool, base_dir: str) -> None:
        super().__init__(id="patch")
        self.mcp = mcp
        self.base_dir = base_dir

    @handler
    async def on_patch(self, req: PatchRequest, ctx: WorkflowContext[BuildResult]) -> None:
        """Apply an LLM-generated patch to the current case."""
        plan_data = ctx.get_state("plan")
        run_dir = ctx.get_state("run_dir")
        assert plan_data is not None, "No plan in workflow state"

        # If no run_dir yet (patching during plan review), we need to build first
        if run_dir is None:
            # Use the base case XML as starting point
            base_xml = ctx.get_state("base_xml") or f"{self.base_dir}/cases/BaseCase_Def.xml"
            current_xml = Path(base_xml).read_text()
        else:
            case_xml = f"{run_dir}/Case_Def.xml"
            current_xml = Path(case_xml).read_text()

        try:
            patch = await _generate_patch(current_xml, plan_data, req.feedback)
            logger.info("LLM patch keys: %s", list(patch.keys()))

            # If no run_dir, do a full initial build with patched plan
            if run_dir is None:
                plan_data = self._merge_patch(plan_data, patch)
                ctx.set_state("plan", plan_data)
                await self._full_build(plan_data, ctx)
                return

            case_xml = f"{run_dir}/Case_Def.xml"

            # Apply geometry patch
            if "geometry_xml" in patch:
                logger.info(">>> set_geometry (patch)")
                r = await self.mcp.call_tool(
                    "set_geometry",
                    base_xml=case_xml,
                    output_xml=case_xml,
                    geometry_xml=patch["geometry_xml"],
                )
                if r.startswith("ERROR"):
                    raise RuntimeError(f"set_geometry failed: {r}")
                plan_data["geometry_xml"] = patch["geometry_xml"]

            # Apply params patch
            if "params" in patch:
                logger.info(">>> modify_xml (patch)")
                # Merge into existing params
                merged_params = {**plan_data["params"], **patch["params"]}
                await self.mcp.call_tool(
                    "modify_xml",
                    base_xml=case_xml,
                    output_xml=case_xml,
                    **merged_params,
                )
                plan_data["params"] = merged_params

            # Apply probe points patch
            if "probe_points" in patch:
                logger.info(">>> generate_points_file (patch)")
                await self.mcp.call_tool(
                    "generate_points_file",
                    output_path=f"{run_dir}/PointsMeasure_Points.txt",
                    probe_points=patch["probe_points"],
                )
                plan_data["probe_points"] = patch["probe_points"]

            ctx.set_state("plan", plan_data)

            # Rebuild gencase + viz
            await rebuild_gencase_viz(self.mcp, run_dir)
            await ctx.send_message(BuildResult(run_dir=run_dir, success=True, message="Patch applied"))

        except Exception as exc:
            logger.exception("Patch failed")
            await ctx.send_message(BuildResult(
                run_dir=run_dir or "",
                success=False,
                message=str(exc),
            ))

    def _merge_patch(self, plan_data: dict, patch: dict) -> dict:
        """Merge patch into plan_data."""
        if "geometry_xml" in patch:
            plan_data["geometry_xml"] = patch["geometry_xml"]
        if "params" in patch:
            plan_data["params"] = {**plan_data["params"], **patch["params"]}
        if "probe_points" in patch:
            plan_data["probe_points"] = patch["probe_points"]
        return plan_data

    async def _full_build(self, plan_data: dict, ctx: WorkflowContext[BuildResult]) -> None:
        """Do a full build when patching without a prior run_dir."""
        from datetime import datetime, timezone

        from agents.schemas import PhysicsParams

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_dir = f"{self.base_dir}/runs/run_{ts}"
        case_xml = f"{run_dir}/Case_Def.xml"

        base_xml = ctx.get_state("base_xml") or f"{self.base_dir}/cases/BaseCase_Def.xml"

        geometry_xml = plan_data.get("geometry_xml")
        params = PhysicsParams(**plan_data["params"])
        probe_points = plan_data["probe_points"]

        # set_geometry
        if geometry_xml:
            r = await self.mcp.call_tool(
                "set_geometry",
                base_xml=base_xml,
                output_xml=case_xml,
                geometry_xml=geometry_xml,
            )
            if r.startswith("ERROR"):
                raise RuntimeError(f"set_geometry failed: {r}")
        else:
            # Copy base XML as-is
            import shutil
            Path(run_dir).mkdir(parents=True, exist_ok=True)
            shutil.copy2(base_xml, case_xml)

        # modify_xml
        await self.mcp.call_tool(
            "modify_xml",
            base_xml=case_xml,
            output_xml=case_xml,
            **params.model_dump(),
        )

        # generate_points_file
        await self.mcp.call_tool(
            "generate_points_file",
            output_path=f"{run_dir}/PointsMeasure_Points.txt",
            probe_points=probe_points,
        )

        # gencase + viz
        await rebuild_gencase_viz(self.mcp, run_dir)

        ctx.set_state("run_dir", run_dir)
        await ctx.send_message(BuildResult(run_dir=run_dir, success=True, message="Patch build complete"))
