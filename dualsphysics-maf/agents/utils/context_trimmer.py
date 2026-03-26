"""Context window management for HITL conversation loops.

Implements a sliding-window strategy that keeps recent messages intact and
summarizes older tool results to prevent unbounded context growth.

Both the setup-review loop (Responses API format) and the results loop
(Chat Completions format) use this module.
"""

import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Maximum number of items to keep in full detail.  Older items beyond this
# window are compressed into one-line summaries.
DEFAULT_MAX_RECENT_ITEMS = 20

# Maximum character length for a single tool-result entry before it is
# truncated in the summary.
_MAX_TOOL_RESULT_CHARS = 300


# ─────────────────────────────────────────────────────────────────────────────
# Chat Completions format  (results loop)
# ─────────────────────────────────────────────────────────────────────────────


def trim_chat_completions_history(
    history: list[dict],
    max_recent: int = DEFAULT_MAX_RECENT_ITEMS,
) -> None:
    """Trim a Chat Completions history list, keeping the system message and
    the most recent *max_recent* non-system items intact.

    Items beyond the window are compressed:
      - tool results  → "OK <tool_call_id> (output truncated)"
      - assistant tool_calls → kept as-is (small; needed for valid history)
      - user messages  → kept as-is (usually small)
      - assistant text → first 200 chars + "… (trimmed)"

    The returned list is always valid for the Chat Completions API: tool
    results still reference the correct tool_call_id, and the ordering of
    assistant → tool messages is preserved.

    Args:
        history: The full conversation history (mutated in-place).
        max_recent: Number of recent non-system items to keep in full.

    Returns:
        None.  The list is mutated in-place.
    """
    if not history:
        return

    # Identify system message (always at index 0 if present)
    has_system = history[0].get("role") == "system"
    start = 1 if has_system else 0
    non_system = history[start:]

    if len(non_system) <= max_recent:
        return  # nothing to trim

    cutoff = len(non_system) - max_recent
    trimmed_count = 0
    for i in range(cutoff):
        item = non_system[i]
        role = item.get("role")

        if role == "tool":
            content = item.get("content", "")
            if len(content) > _MAX_TOOL_RESULT_CHARS:
                # Summarize: keep first line, indicate truncation
                first_line = content.split("\n", 1)[0][:200]
                item["content"] = f"{first_line}… (output trimmed, {len(content)} chars original)"
                trimmed_count += 1

        elif role == "assistant" and item.get("content"):
            content = item["content"]
            if len(content) > _MAX_TOOL_RESULT_CHARS:
                item["content"] = content[:200] + "… (trimmed)"
                trimmed_count += 1

        # user messages and assistant tool_calls are left intact

    if trimmed_count:
        logger.info(
            "Trimmed %d old items in Chat Completions history (window=%d, total=%d)",
            trimmed_count, max_recent, len(history),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Responses API format  (setup review loop)
# ─────────────────────────────────────────────────────────────────────────────


def trim_responses_api_history(
    history: list[dict],
    max_recent: int = DEFAULT_MAX_RECENT_ITEMS,
) -> None:
    """Trim a Responses API history list, keeping the most recent
    *max_recent* items intact and summarizing older ones.

    Responses API items use ``type`` rather than ``role``:
      - ``{"type": "message", "role": "user", …}``
      - ``{"type": "message", "role": "assistant", …}``
      - ``{"type": "function_call", …}``
      - ``{"type": "function_call_output", …}``

    Items beyond the window are compressed in the same spirit as the Chat
    Completions trimmer: function_call_output content is truncated, and
    assistant message text is shortened.

    Args:
        history: The full Responses API input list (mutated in-place).
        max_recent: Number of recent items to keep in full.

    Returns:
        None.  The list is mutated in-place.
    """
    if len(history) <= max_recent:
        return

    cutoff = len(history) - max_recent
    trimmed_count = 0
    for i in range(cutoff):
        item = history[i]
        item_type = item.get("type")

        if item_type == "function_call_output":
            output = item.get("output", "")
            if len(output) > _MAX_TOOL_RESULT_CHARS:
                first_line = output.split("\n", 1)[0][:200]
                item["output"] = f"{first_line}… (output trimmed, {len(output)} chars original)"
                trimmed_count += 1

        elif item_type == "message" and item.get("role") == "assistant":
            for block in item.get("content", []):
                if block.get("type") == "output_text":
                    text = block.get("text", "")
                    if len(text) > _MAX_TOOL_RESULT_CHARS:
                        block["text"] = text[:200] + "… (trimmed)"
                        trimmed_count += 1

        # user messages and function_call items are left intact

    if trimmed_count:
        logger.info(
            "Trimmed %d old items in Responses API history (window=%d, total=%d)",
            trimmed_count, max_recent, len(history),
        )
