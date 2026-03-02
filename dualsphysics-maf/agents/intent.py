"""LLM-based intent classification and Q&A for HITL feedback.

Uses GPT-4o-mini to classify user feedback into three intents:
  - approve: user wants to proceed
  - revise:  user wants changes (loop back to planning)
  - question: user is asking a question about the plan
"""

import json
import logging
from pathlib import Path

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_CLASSIFY_SYSTEM_PROMPT = (
    "You are a classifier. The user has been shown a simulation plan or "
    "geometry visualization and replied with the message below. Classify "
    "the user's intent into exactly one of three categories.\n\n"
    "Return JSON with a single key: {\"intent\": \"approve\"}, "
    "{\"intent\": \"revise\"}, or {\"intent\": \"question\"}.\n\n"
    "### approve\n"
    "The user wants to proceed with the current plan.\n"
    "Examples: 'yes', 'ok', 'looks good', 'go ahead', 'proceed', "
    "'that works', 'approved', 'lgtm', 'go ahead with the next step', ''.\n\n"
    "### revise\n"
    "The user wants to change something about the plan.\n"
    "Examples: 'make it wider', 'change the density', 'the channel "
    "is too short', 'try a higher yield stress', 'no', 'use a longer channel'.\n\n"
    "### question\n"
    "The user is asking a question or requesting an explanation.\n"
    "Examples: 'why did you choose this density?', 'what is HBP_n?', "
    "'explain the probe placement', 'what does tau_yield mean?', "
    "'why is gravity set to -9.81?', 'how did you decide on the channel length?'."
)

_SKILL_FILE = Path(__file__).resolve().parent.parent / "skills" / "dualsphysics_xml_guide.md"


async def classify_intent(feedback: str) -> str:
    """Classify user feedback as ``"approve"``, ``"revise"``, or ``"question"``.

    Empty feedback is treated as ``"approve"``.
    """
    feedback = feedback.strip()
    if not feedback:
        return "approve"

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
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
    if intent not in ("approve", "revise", "question"):
        logger.warning("Unexpected intent %r, defaulting to 'approve'", intent)
        intent = "approve"
    logger.info("classify_intent(%r) -> %s", feedback, intent)
    return intent


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
        model="gpt-4o-mini",
        temperature=0.3,
        messages=[
            {"role": "system", "content": "\n".join(system_parts)},
            {"role": "user", "content": question},
        ],
    )

    answer = response.choices[0].message.content or "I'm not sure — please rephrase."
    logger.info("answer_question(%r) -> %d chars", question, len(answer))
    return answer
