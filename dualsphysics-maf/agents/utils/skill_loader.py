"""Shared skill content loader for non-Agent callers (patch, intent Q&A).

These callers use raw AsyncOpenAI and don't go through SkillsProvider,
so they need to read the skill files directly from disk.
"""

from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "dualsphysics-xml"


def load_all_skill_content() -> str:
    """Read and concatenate all skill content from the dualsphysics-xml directory.

    Returns the SKILL.md body followed by all resource files, separated by
    horizontal rules. Content is cached after first read.
    """
    parts: list[str] = []

    # SKILL.md first
    skill_md = SKILL_DIR / "SKILL.md"
    if skill_md.exists():
        parts.append(skill_md.read_text(encoding="utf-8"))

    # Then all resource .md files (sorted for determinism)
    for md_file in sorted(SKILL_DIR.glob("*.md")):
        if md_file.name == "SKILL.md":
            continue
        parts.append(md_file.read_text(encoding="utf-8"))

    return "\n\n---\n\n".join(parts)


# Module-level cache: read once at import time
_cached_content: str | None = None


def get_skill_content() -> str:
    """Return cached skill content (reads from disk on first call)."""
    global _cached_content
    if _cached_content is None:
        _cached_content = load_all_skill_content()
    return _cached_content
