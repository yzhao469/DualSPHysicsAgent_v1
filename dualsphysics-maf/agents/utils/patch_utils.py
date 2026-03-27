"""Shared patch utilities — LLM-driven XML patching and plan merging.

Extracted from the old PatchExecutor for reuse by SetupReviewExecutor.
"""

import json
import logging
import os

from openai import AsyncOpenAI

from agents.utils.skill_loader import get_skill_content

logger = logging.getLogger(__name__)

PATCH_SYSTEM_PROMPT = """\
You are an expert DualSPHysics simulation engineer. You will be given:
1. The current Case_Def.xml for a simulation case.
2. The current simulation plan (geometry_xml, params).
3. A user instruction describing what to change.

Return a JSON object with ONLY the keys that need to change. Possible keys:
- "geometry_xml": string — full <geometry>...</geometry> XML block (only if geometry changes)
- "params": object — only the physics parameter fields that change (partial update)

Do NOT include keys that don't need to change. If only density changes, return {"params": {"rhop0": 2000, "phase_rhop": 2000}}.
Return valid JSON only, no markdown fences.
"""


async def generate_patch(
    current_xml: str,
    plan_data: dict,
    feedback: str,
) -> dict:
    """Call LLM to produce a targeted patch."""
    skill_text = f"\n\n### Reference Material\n{get_skill_content()}"

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
            {"role": "system", "content": PATCH_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)


def merge_patch(plan_data: dict, patch: dict) -> dict:
    """Merge a patch dict into plan_data (mutates and returns plan_data)."""
    if "geometry_xml" in patch:
        plan_data["geometry_xml"] = patch["geometry_xml"]
    if "params" in patch:
        plan_data["params"] = {**plan_data["params"], **patch["params"]}
    return plan_data
