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


async def resolve_datalake_file(scenario: str, available_files: list[str]) -> str | None:
    """Ask GPT-4o-mini whether the user's scenario references a datalake file.

    Args:
        scenario: The user's natural-language scenario.
        available_files: List of relative paths (e.g. ["datalake/Case_Def.xml"]).

    Returns:
        The matched relative path, or None if the user isn't referencing a file.
    """
    if not available_files:
        return None

    file_list = "\n".join(f"  - {f}" for f in available_files)
    system = (
        "You are a file-reference resolver. The user is describing a simulation scenario. "
        "Determine if they are referencing an existing case file from the list below.\n\n"
        f"Available files:\n{file_list}\n\n"
        "Return JSON with a single key: {\"file\": \"<relative_path>\"} if the user is "
        "referencing one of the files above (use fuzzy matching — e.g. 'MyCase' could match "
        "'Case_Def.xml' if it's the only plausible match). "
        "Return {\"file\": null} if the user is NOT referencing any existing file."
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

    raw = response.choices[0].message.content or '{"file": null}'
    result = json.loads(raw)
    matched = result.get("file")
    if matched and matched in available_files:
        logger.info("resolve_datalake_file(%r) -> %s", scenario, matched)
        return matched
    logger.info("resolve_datalake_file(%r) -> None", scenario)
    return None


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
