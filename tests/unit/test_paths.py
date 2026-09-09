"""Bundled-resource resolution must not depend on the package's depth."""
from pathlib import Path

from cortex import paths
from support import REPO_ROOT


def test_skills_dir_resolves_to_a_real_directory():
    assert paths.skills_dir().is_dir()


def test_skills_dir_contains_the_skills():
    names = {p.name for p in paths.skills_dir().iterdir() if p.is_dir()}
    assert "cortex-tracking" in names
    assert "cortex-sync" in names


def test_commands_dir_resolves_to_a_real_directory():
    assert (paths.commands_dir() / "close-day.md").is_file()


def test_run_from_clone_resolves_to_the_repo_root():
    """With no packaged copy inside the package, it falls back to the repo."""
    assert paths.skills_dir() == REPO_ROOT / "skills"


def test_bundled_dir_prefers_a_packaged_copy(monkeypatch, tmp_path):
    """Inside a wheel, skills/ sits next to cli.py rather than two levels up."""
    fake_pkg = tmp_path / "cortex"
    (fake_pkg / "skills" / "cortex-tracking").mkdir(parents=True)
    monkeypatch.setattr(paths, "_PACKAGE_ROOT", fake_pkg)
    assert paths.bundled_dir("skills") == fake_pkg / "skills"


def test_sync_template_resolves():
    from cortex.sync import setup
    assert setup._TEMPLATE_GITIGNORE.is_file()
