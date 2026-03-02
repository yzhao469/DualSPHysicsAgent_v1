"""LLM-based intent classification for HITL feedback.

Uses GPT-4o-mini to classify whether user feedback is an approval
(proceed) or a revision request (loop back to planning).
"""

import json
import logging

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a classifier. The user has been shown a simulation plan or "
    "geometry visualization and replied with the message below. Determine "
    "whether the user is APPROVING (wants to proceed) or REQUESTING REVISION "
    "(wants changes). Return JSON: {\"approved\": true} or {\"approved\": false}.\n\n"
    "Examples of approval: 'yes', 'ok', 'looks good', 'go ahead', 'proceed', "
    "'that works', 'approved', 'lgtm', 'go ahead with the next step', ''.\n"
    "Examples of revision: 'make it wider', 'change the density', 'the channel "
    "is too short', 'try a higher yield stress', 'no'."
)


async def classify_intent(feedback: str) -> bool:
    """Classify user feedback as approval (True) or revision (False).

    Empty feedback is treated as approval.
    """
    feedback = feedback.strip()
    if not feedback:
        return True

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": feedback},
        ],
    )

    raw = response.choices[0].message.content or '{"approved": true}'
    result = json.loads(raw)
    approved = result.get("approved", True)
    logger.info("classify_intent(%r) -> approved=%s", feedback, approved)
    return approved
