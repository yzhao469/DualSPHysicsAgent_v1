"""Tests for context_trimmer utilities."""

import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_skill_loader():
    """Provide a minimal agents.utils.skill_loader stub so context_trimmer can import."""
    agents_pkg = types.ModuleType("agents")
    agents_pkg.__path__ = []
    utils_pkg = types.ModuleType("agents.utils")
    utils_pkg.__path__ = []

    prev = {
        "agents": sys.modules.get("agents"),
        "agents.utils": sys.modules.get("agents.utils"),
    }
    sys.modules.setdefault("agents", agents_pkg)
    sys.modules.setdefault("agents.utils", utils_pkg)
    yield
    for name, orig in prev.items():
        if orig is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = orig


from agents.utils.context_trimmer import (
    DEFAULT_MAX_RECENT_ITEMS,
    trim_chat_completions_history,
    trim_responses_api_history,
)


# ─────────────────────────────────────────────────────────────────────────────
# Chat Completions format
# ─────────────────────────────────────────────────────────────────────────────


class TestTrimChatCompletionsHistory:
    def test_no_trim_when_under_limit(self):
        history = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = trim_chat_completions_history(history, max_recent=10)
        assert result is history
        assert result[1]["content"] == "hello"
        assert result[2]["content"] == "hi"

    def test_trims_old_tool_results(self):
        history = [
            {"role": "system", "content": "sys"},
        ]
        # Add old items that will be beyond the window
        for i in range(10):
            history.append({"role": "user", "content": f"q{i}"})
            history.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": f"tc_{i}", "function": {"name": "f", "arguments": "{}"}}],
            })
            history.append({
                "role": "tool",
                "tool_call_id": f"tc_{i}",
                "content": "x" * 500,  # long tool result
            })

        total_before = len(history)
        trim_chat_completions_history(history, max_recent=6)

        # Total items unchanged (in-place mutation)
        assert len(history) == total_before
        # Old tool results should be trimmed
        old_tool = history[3]  # first tool result (index 3 = sys + user + assistant + tool)
        assert old_tool["role"] == "tool"
        assert "trimmed" in old_tool["content"]
        assert len(old_tool["content"]) < 500

        # Recent items should be intact
        last_tool = history[-1]
        assert last_tool["role"] == "tool"
        assert len(last_tool["content"]) == 500  # untrimmed

    def test_trims_old_assistant_text(self):
        history = [
            {"role": "system", "content": "sys"},
        ]
        for i in range(10):
            history.append({"role": "user", "content": f"q{i}"})
            history.append({"role": "assistant", "content": "a" * 500})

        trim_chat_completions_history(history, max_recent=4)

        # Old assistant content should be trimmed
        old_assistant = history[2]  # sys + user + assistant
        assert old_assistant["role"] == "assistant"
        assert "trimmed" in old_assistant["content"]

    def test_preserves_user_messages(self):
        history = [
            {"role": "system", "content": "sys"},
        ]
        for i in range(10):
            history.append({"role": "user", "content": f"long message {'x' * 500}"})
            history.append({"role": "assistant", "content": "ok"})

        trim_chat_completions_history(history, max_recent=4)

        # User messages should NOT be trimmed
        old_user = history[1]
        assert old_user["role"] == "user"
        assert len(old_user["content"]) > 500

    def test_empty_history(self):
        history = []
        result = trim_chat_completions_history(history)
        assert result == []

    def test_system_only(self):
        history = [{"role": "system", "content": "sys"}]
        result = trim_chat_completions_history(history, max_recent=5)
        assert len(result) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Responses API format
# ─────────────────────────────────────────────────────────────────────────────


class TestTrimResponsesApiHistory:
    def test_no_trim_when_under_limit(self):
        history = [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]},
        ]
        result = trim_responses_api_history(history, max_recent=5)
        assert result is history
        assert len(result) == 1

    def test_trims_old_function_call_output(self):
        history = []
        for i in range(10):
            history.append(
                {"type": "message", "role": "user", "content": [{"type": "input_text", "text": f"q{i}"}]}
            )
            history.append(
                {"type": "function_call", "id": f"fc_{i}", "call_id": f"c_{i}", "name": "f", "arguments": "{}"}
            )
            history.append(
                {"type": "function_call_output", "call_id": f"c_{i}", "output": "x" * 500}
            )

        trim_responses_api_history(history, max_recent=6)

        # Old function_call_output should be trimmed
        old_output = history[2]  # user + fc + output
        assert old_output["type"] == "function_call_output"
        assert "trimmed" in old_output["output"]

        # Recent should be intact
        last_output = history[-1]
        assert last_output["type"] == "function_call_output"
        assert len(last_output["output"]) == 500

    def test_trims_old_assistant_text(self):
        history = []
        for i in range(10):
            history.append(
                {"type": "message", "role": "user", "content": [{"type": "input_text", "text": f"q{i}"}]}
            )
            history.append(
                {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "a" * 500}]}
            )

        trim_responses_api_history(history, max_recent=4)

        old_assistant = history[1]
        assert old_assistant["type"] == "message"
        assert old_assistant["role"] == "assistant"
        assert "trimmed" in old_assistant["content"][0]["text"]

    def test_empty_history(self):
        result = trim_responses_api_history([])
        assert result == []
