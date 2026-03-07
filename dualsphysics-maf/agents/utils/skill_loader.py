"""Shared skill content loader for non-Agent callers (patch, intent Q&A, analyze).

These callers use raw AsyncOpenAI and don't go through SkillsProvider,
so they need to read the skill files directly from disk.
"""

from pathlib import Path

_SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent / "skills"


def _load_skill_dir(skill_dir: Path) -> str:
    """Read and concatenate all markdown from a skill directory.

    Returns the SKILL.md body followed by all resource files, separated by
    horizontal rules.
    """
    parts: list[str] = []

    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        parts.append(skill_md.read_text(encoding="utf-8"))

    for md_file in sorted(skill_dir.glob("*.md")):
        if md_file.name == "SKILL.md":
            continue
        parts.append(md_file.read_text(encoding="utf-8"))

    return "\n\n---\n\n".join(parts)


# Module-level caches
_cached: dict[str, str] = {}


def get_skill_content() -> str:
    """Return cached geometry/XML skill content."""
    if "xml" not in _cached:
        _cached["xml"] = _load_skill_dir(_SKILLS_ROOT / "dualsphysics-xml")
    return _cached["xml"]


def get_postprocess_skill_content() -> str:
    """Return cached post-processing skill content."""
    if "postprocess" not in _cached:
        _cached["postprocess"] = _load_skill_dir(_SKILLS_ROOT / "dualsphysics-postprocess")
    return _cached["postprocess"]
