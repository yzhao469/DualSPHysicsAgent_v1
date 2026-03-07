import pytest

from agents.utils import skill_loader

pytestmark = pytest.mark.unit


def test_load_skill_dir_reads_skill_then_sorted_resources(tmp_path):
    skill_dir = tmp_path / "dualsphysics-xml"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("main skill", encoding="utf-8")
    (skill_dir / "zeta.md").write_text("zeta resource", encoding="utf-8")
    (skill_dir / "alpha.md").write_text("alpha resource", encoding="utf-8")

    assert skill_loader._load_skill_dir(skill_dir) == (
        "main skill\n\n---\n\nalpha resource\n\n---\n\nzeta resource"
    )


def test_get_skill_content_uses_cache(monkeypatch, tmp_path):
    skills_root = tmp_path / "skills"
    xml_dir = skills_root / "dualsphysics-xml"
    xml_dir.mkdir(parents=True)
    (xml_dir / "SKILL.md").write_text("first version", encoding="utf-8")

    monkeypatch.setattr(skill_loader, "_SKILLS_ROOT", skills_root)
    skill_loader._cached.clear()

    first = skill_loader.get_skill_content()
    (xml_dir / "SKILL.md").write_text("second version", encoding="utf-8")
    second = skill_loader.get_skill_content()

    assert first == "first version"
    assert second == "first version"


def test_get_postprocess_skill_content_reads_postprocess_bundle(monkeypatch, tmp_path):
    skills_root = tmp_path / "skills"
    postprocess_dir = skills_root / "dualsphysics-postprocess"
    postprocess_dir.mkdir(parents=True)
    (postprocess_dir / "SKILL.md").write_text("postprocess skill", encoding="utf-8")
    (postprocess_dir / "plots.md").write_text("plot recipes", encoding="utf-8")

    monkeypatch.setattr(skill_loader, "_SKILLS_ROOT", skills_root)
    skill_loader._cached.clear()

    assert skill_loader.get_postprocess_skill_content() == (
        "postprocess skill\n\n---\n\nplot recipes"
    )
