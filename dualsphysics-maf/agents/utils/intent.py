"""LLM-based intent classification and Q&A for HITL feedback.

Uses GPT-4o-mini to classify user feedback into five intents:
  - approve:      user wants to proceed
  - agent_patch:  user wants targeted changes (LLM patches current XML)
  - manual_edit:  user wants to edit the XML file themselves
  - question:     user is asking a question about the plan
  - full_replan:  user wants to scrap everything and start over
"""

import json
import logging
import os
from pathlib import Path

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_CLASSIFY_SYSTEM_PROMPT = (
    "You are a classifier. The user has been shown a simulation plan or "
    "geometry visualization and replied with the message below. Classify "
    "the user's intent into exactly one of five categories.\n\n"
    "Return JSON with a single key: {\"intent\": \"<category>\"}.\n\n"
    "### approve\n"
    "The user wants to proceed with the current plan as-is.\n"
    "Examples: 'yes', 'ok', 'looks good', 'go ahead', 'proceed', "
    "'that works', 'approved', 'lgtm', 'go ahead with the next step', ''.\n\n"
    "### agent_patch\n"
    "The user wants a targeted change to the current plan — they describe "
    "what to modify but do NOT want to start over.\n"
    "Examples: 'make it wider', 'change the density to 2000', 'the channel "
    "is too short', 'try a higher yield stress', 'no, use a longer channel', "
    "'move the probes further downstream'.\n\n"
    "### manual_edit\n"
    "The user wants to manually edit the XML file themselves.\n"
    "Examples: 'let me edit it', 'I want to edit the file myself', "
    "'I will modify the XML manually', 'open the file for me to edit'.\n\n"
    "### question\n"
    "The user is asking a question or requesting an explanation.\n"
    "Examples: 'why did you choose this density?', 'what is HBP_n?', "
    "'explain the probe placement', 'what does tau_yield mean?', "
    "'why is gravity set to -9.81?', 'how did you decide on the channel length?'.\n\n"
    "### full_replan\n"
    "The user wants to scrap the current plan entirely and start from scratch "
    "with a fundamentally different scenario.\n"
    "Examples: 'start over', 'scrap this', 'let's do a dam break instead', "
    "'forget this, simulate something completely different', 'redo everything'."
)

_SKILL_FILE = Path(__file__).resolve().parent.parent.parent / "skills" / "dualsphysics_xml_guide.md"


_VALID_INTENTS = {"approve", "agent_patch", "manual_edit", "question", "full_replan"}


async def classify_intent(feedback: str) -> str:
    """Classify user feedback into one of five intents.

    Valid intents: ``"approve"``, ``"agent_patch"``, ``"manual_edit"``,
    ``"question"``, ``"full_replan"``.

    Empty feedback is treated as ``"approve"``.
    """
    feedback = feedback.strip()
    if not feedback:
        return "approve"

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=os.getenv("INTENT_MODEL", "gpt-4o-mini"),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": feedback},
        ],
    )

    raw = response.choices[0].message.content or '{"intent": "approve"}'
    result = json.loads(raw)
    intent = result.get("intent", "approve")
    if intent not in _VALID_INTENTS:
        logger.warning("Unexpected intent %r, defaulting to 'approve'", intent)
        intent = "approve"
    logger.info("classify_intent(%r) -> %s", feedback, intent)
    return intent


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


async def answer_question(question: str, plan_context: str) -> str:
    """Answer a user question about the simulation plan using GPT-4o-mini.

    Provides the plan context and the skill file as reference material.
    """
    skill_text = ""
    if _SKILL_FILE.exists():
        skill_text = _SKILL_FILE.read_text()

    system_parts = [
        "You are a helpful assistant that answers questions about a DualSPHysics "
        "simulation plan. Use the plan context and reference material below to "
        "give a clear, concise answer.\n",
        "### Current Simulation Plan\n",
        plan_context,
    ]
    if skill_text:
        system_parts += [
            "\n\n### Reference Material (DualSPHysics XML Guide)\n",
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
