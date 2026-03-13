"""Append-only chat logger — writes one JSONL line per message to run_dir/chat_history.jsonl.

Works identically for terminal (main.py) and GUI (gui_api.py) entry points
because logging happens inside the workflow executors.
"""

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def log_message(
    run_dir: str,
    role: str,
    content: str,
    phase: str = "",
) -> None:
    """Append a single message to ``{run_dir}/chat_history.jsonl``.

    Args:
        run_dir: Absolute path to the run directory (e.g. ``runs/run_20260312_…``).
        role: ``"user"`` | ``"assistant"`` | ``"system"``
        content: The message text.
        phase: Workflow phase (``"planning"``, ``"setup_review"``, ``"results_loop"``).
    """
    if not run_dir:
        return
    try:
        os.makedirs(run_dir, exist_ok=True)
        path = os.path.join(run_dir, "chat_history.jsonl")
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "phase": phase,
            "role": role,
            "content": content,
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("Failed to write chat log to %s", run_dir, exc_info=True)
