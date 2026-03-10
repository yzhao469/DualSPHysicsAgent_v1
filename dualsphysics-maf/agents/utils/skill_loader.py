"""Shared skill content loader for non-Agent callers (patch, intent Q&A, analyze).

These callers use raw AsyncOpenAI and don't go through SkillsProvider,
so they need to read the skill files directly from disk.
"""

from pathlib import Path

_SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent / "skills"

# Topic registry: human-readable name -> (skill_dir, filename)
_TOPIC_REGISTRY: dict[str, tuple[str, str]] = {
    "postprocess-overview":    ("dualsphysics-postprocess", "SKILL.md"),
    "partvtk":                 ("dualsphysics-postprocess", "partvtk-help.md"),
    "isosurface":              ("dualsphysics-postprocess", "isosurface-help.md"),
    "other-postprocess-tools": ("dualsphysics-postprocess", "other-tools-help.md"),
    "xml-overview":            ("dualsphysics-xml", "SKILL.md"),
    "drawing-primitives":      ("dualsphysics-xml", "drawing-primitives.md"),
    "transforms-and-advanced": ("dualsphysics-xml", "transforms-and-advanced.md"),
    "composition-patterns":    ("dualsphysics-xml", "composition-patterns.md"),
}


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


def get_skill_topic(topic: str) -> str:
    """Load and cache a single skill file by topic name.

    Raises ValueError for unknown topics.
    """
    if topic not in _TOPIC_REGISTRY:
        raise ValueError(
            f"Unknown skill topic {topic!r}. "
            f"Available: {sorted(_TOPIC_REGISTRY)}"
        )
    cache_key = f"topic:{topic}"
    if cache_key not in _cached:
        skill_dir, filename = _TOPIC_REGISTRY[topic]
        path = _SKILLS_ROOT / skill_dir / filename
        _cached[cache_key] = path.read_text(encoding="utf-8")
    return _cached[cache_key]


def list_skill_topics(domain: str = "all") -> list[str]:
    """Return topic names filtered by domain.

    Args:
        domain: "postprocess", "xml", or "all".
    """
    if domain == "all":
        return sorted(_TOPIC_REGISTRY)
    prefix_map = {"postprocess": "dualsphysics-postprocess", "xml": "dualsphysics-xml"}
    dir_name = prefix_map.get(domain)
    if dir_name is None:
        raise ValueError(f"Unknown domain {domain!r}. Use 'postprocess', 'xml', or 'all'.")
    return sorted(k for k, (d, _) in _TOPIC_REGISTRY.items() if d == dir_name)
