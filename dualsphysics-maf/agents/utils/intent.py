"""LLM-based Q&A and datalake file resolution for HITL feedback.

Used by SetupReviewExecutor and ResultsLoopExecutor for answering
questions, and by PlanningExecutor for datalake file matching.
"""

import json
import logging
import os

from openai import AsyncOpenAI

from agents.utils.skill_loader import get_postprocess_skill_content, get_skill_content

logger = logging.getLogger(__name__)


async def resolve_datalake_files(scenario: str, available_files: list[str]) -> list[str]:
    """Ask the LLM which datalake files are relevant to the user's scenario.

    Args:
        scenario: The user's natural-language scenario.
        available_files: List of relative paths (e.g. ["datalake/Case_Def.xml"]).

    Returns:
        List of matched relative paths (may be empty).
    """
    if not available_files:
        return []

    file_list = "\n".join(f"  - {f}" for f in available_files)
    system = (
        "You are a file-reference resolver. The user is describing a simulation scenario. "
        "Determine which files from the list below are relevant to their scenario.\n\n"
        f"Available files:\n{file_list}\n\n"
        "Return JSON: {\"files\": [\"<path1>\", \"<path2>\", ...]}.\n\n"
        "Rules:\n"
        "1. If the user explicitly names a file (e.g. '1.png', 'Case_Def.xml'), return ONLY that file. "
        "Do NOT add other files based on topic similarity.\n"
        "2. Only use fuzzy/topic matching when the user does NOT name a specific file.\n"
        "3. Return {\"files\": []} if no files are relevant."
    )

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=os.getenv("INTENT_MODEL", "gpt-4o-mini"),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": scenario},
        ],
    )

    raw = response.choices[0].message.content or '{"files": []}'
    result = json.loads(raw)
    matched = [f for f in result.get("files", []) if f in available_files]
    logger.info("resolve_datalake_files(%r) -> %s", scenario, matched)
    return matched


async def answer_question(question: str, plan_context: str, domain: str = "xml") -> str:
    """Answer a user question about the simulation plan using GPT-4o-mini.

    Provides the plan context and the skill file as reference material.

    Args:
        domain: "xml" for geometry/setup skills, "postprocess" for analysis skills.
    """
    if domain == "postprocess":
        skill_text = get_postprocess_skill_content()
        ref_label = "Post-Processing Guide"
    else:
        skill_text = get_skill_content()
        ref_label = "DualSPHysics XML Guide"

    system_parts = [
        "You are a helpful assistant that answers questions about a DualSPHysics "
        "simulation plan. Use the plan context and reference material below to "
        "give a clear, concise answer.\n",
        "### Current Simulation Plan\n",
        plan_context,
        f"\n\n### Reference Material ({ref_label})\n",
        skill_text,
    ]

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=os.getenv("INTENT_MODEL", "gpt-4o-mini"),
        temperature=0.3,
        messages=[
            {"role": "system", "content": "\n".join(system_parts)},
            {"role": "user", "content": question},
        ],
    )

    answer = response.choices[0].message.content or "I'm not sure — please rephrase."
    logger.info("answer_question(%r) -> %d chars", question, len(answer))
    return answer
