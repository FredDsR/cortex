import dataclasses

import pytest

from cortex.install.harnesses import (
    CURRENT_SKILL_NAMES,
    HARNESSES,
    LEGACY_SKILL_NAMES,
    Harness,
    install_targets,
)


def test_install_targets_are_a_subset_of_all_harnesses():
    """Uninstall must reach every harness install can create, or an install
    becomes unremovable."""
    assert set(install_targets()) <= set(HARNESSES)


def test_gemini_cli_is_uninstall_only():
    """Dropped as an install target in c2c399a, retained so older installs
    can still be cleaned up."""
    gemini = next(h for h in HARNESSES if h.name == "gemini-cli")
    assert gemini.install is False


def test_current_install_targets():
    assert [h.name for h in install_targets()] == [
        "claude-code", "codex", "copilot-cli",
    ]


def test_skills_rel_is_relative_and_ends_in_skills():
    for h in HARNESSES:
        assert not h.skills_rel.startswith("/")
        assert h.skills_rel.endswith("/skills")


def test_root_rel_strips_the_skills_segment():
    assert Harness("x", ".x/skills", install=True).root_rel == ".x"


def test_harness_is_hashable_and_frozen():
    h = Harness("x", ".x/skills", install=True)
    assert hash(h)
    with pytest.raises(dataclasses.FrozenInstanceError):
        h.name = "y"


def test_legacy_names_are_the_pre_rebrand_set():
    assert "tracking-work" in LEGACY_SKILL_NAMES
    assert not any(n.startswith("cortex-") for n in LEGACY_SKILL_NAMES)


def test_current_names_cover_every_shipped_skill():
    """A skill added to the repo but not to this tuple would be installed and
    then never uninstalled."""
    from cortex.paths import skills_dir
    shipped = {p.name for p in skills_dir().iterdir()
               if (p / "SKILL.md").is_file()}
    assert shipped == set(CURRENT_SKILL_NAMES)
