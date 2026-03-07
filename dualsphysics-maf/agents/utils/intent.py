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

from openai import AsyncOpenAI

from agents.utils.skill_loader import get_skill_content

logger = logging.getLogger(__name__)

_CLASSIFY_SYSTEM_PROMPT_PLAN = (
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

_CLASSIFY_SYSTEM_PROMPT_RESULTS = (
    "You are a classifier. The user has just completed a DualSPHysics simulation "
    "and is reviewing the results. They can request further analysis or finish. "
    "Classify the user's intent into exactly one of five categories.\n\n"
    "Return JSON with a single key: {\"intent\": \"<category>\"}.\n\n"
    "### approve\n"
    "The user is done and wants to finish.\n"
    "Examples: 'done', 'that is all', 'finished', 'exit', 'no more analysis', "
    "'I am satisfied', 'nothing else', ''.\n\n"
    "### agent_patch\n"
    "The user wants to perform analysis, visualization, or data extraction on "
    "the simulation results. This includes ANY request that requires reading, "
    "computing, or processing actual simulation data — even if phrased as a "
    "question. If answering the request requires looking at the data files, "
    "this is agent_patch, NOT question.\n"
    "Examples: 'visualize the results', 'show me the flow', 'plot the velocity', "
    "'what is the run-out distance?', 'export fluid particles as CSV', "
    "'compute forces on the obstacle', 'show the free surface', "
    "'can you visualize the result for me?', 'extract the max velocity over time', "
    "'plot pressure at the probes', 'generate VTK files for ParaView', "
    "'what is the average velocity?', 'what is the max pressure?', "
    "'how far did the debris travel?', 'what are the values in the CSV?', "
    "'what is the average value of velocity x', 'show me the probe data'.\n\n"
    "### question\n"
    "The user is asking a purely conceptual or definitional question that can "
    "be answered from general knowledge alone, WITHOUT reading any data files.\n"
    "Examples: 'what does RMSE mean?', 'is this a good result?', "
    "'what units are the velocities in?', 'how do I open VTK files?', "
    "'what does each column mean in the CSV?', 'what is HBP model?'.\n\n"
    "### full_replan\n"
    "The user wants to discard results and re-run with different parameters.\n"
    "Examples: 'let me try different parameters', 'start over with higher density', "
    "'redo the simulation', 'scrap this and try again'.\n\n"
    "### manual_edit\n"
    "Not applicable in results phase — classify as agent_patch instead."
)


_VALID_INTENTS = {"approve", "agent_patch", "manual_edit", "question", "full_replan"}


async def classify_intent(feedback: str, phase: str = "plan") -> str:
    """Classify user feedback into one of five intents.

    Valid intents: ``"approve"``, ``"agent_patch"``, ``"manual_edit"``,
    ``"question"``, ``"full_replan"``.

    Empty feedback is treated as ``"approve"``.

    Args:
        feedback: The user's reply text.
        phase: Review phase — ``"plan"``, ``"viz"``, or ``"results"``.
               Uses a phase-specific system prompt for better classification.
    """
    feedback = feedback.strip()
    if not feedback:
        return "approve"

    system_prompt = (
        _CLASSIFY_SYSTEM_PROMPT_RESULTS if phase == "results"
        else _CLASSIFY_SYSTEM_PROMPT_PLAN
    )

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=os.getenv("INTENT_MODEL", "gpt-4o-mini"),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
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
    skill_text = get_skill_content()

    system_parts = [
        "You are a helpful assistant that answers questions about a DualSPHysics "
        "simulation plan. Use the plan context and reference material below to "
        "give a clear, concise answer.\n",
        "### Current Simulation Plan\n",
        plan_context,
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
