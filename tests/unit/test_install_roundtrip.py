import pytest

from cortex.install.links import install_skills, uninstall_skills


@pytest.fixture
def repo(tmp_path):
    src = tmp_path / "repo" / "skills"
    for name in ("cortex-tracking", "cortex-kb"):
        d = src / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    return tmp_path / "repo"


def test_install_then_uninstall_leaves_nothing_behind(tmp_path, repo):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)

    install_skills(skills_src=repo / "skills", target_root=home, home=home)
    dest = home / ".claude" / "skills"
    assert (dest / "cortex-kb").is_symlink()

    removed, kept = uninstall_skills(target_root=home, owner_root=repo)
    assert not (dest / "cortex-kb").is_symlink()
    assert not (dest / "cortex-tracking").is_symlink()
    assert kept == []
    assert len(removed) == 2


def test_uninstall_keeps_a_foreign_symlink(tmp_path, repo):
    home = tmp_path / "home"
    dest = home / ".claude" / "skills"
    dest.mkdir(parents=True)
    foreign = dest / "cortex-kb"
    foreign.symlink_to(tmp_path / "someone-elses-repo" / "cortex-kb")

    removed, kept = uninstall_skills(target_root=home, owner_root=repo)
    assert foreign.is_symlink()
    assert removed == []
    assert len(kept) == 1


def test_uninstall_keeps_a_real_directory(tmp_path, repo):
    home = tmp_path / "home"
    dest = home / ".claude" / "skills"
    dest.mkdir(parents=True)
    mine = dest / "cortex-kb"
    mine.mkdir()
    (mine / "SKILL.md").write_text("hand written")

    removed, kept = uninstall_skills(target_root=home, owner_root=repo)
    assert (mine / "SKILL.md").read_text() == "hand written"
    assert removed == []
    assert len(kept) == 1


def test_uninstall_reaches_the_legacy_gemini_target(tmp_path, repo):
    """gemini-cli is not an install target, but an old install may have left
    links there and uninstall must still clean them."""
    home = tmp_path / "home"
    dest = home / ".gemini" / "skills"
    dest.mkdir(parents=True)
    (dest / "cortex-kb").symlink_to(repo / "skills" / "cortex-kb")

    removed, _ = uninstall_skills(target_root=home, owner_root=repo)
    assert not (dest / "cortex-kb").is_symlink()
    assert len(removed) == 1


def test_uninstall_removes_pre_rebrand_names(tmp_path, repo):
    home = tmp_path / "home"
    dest = home / ".claude" / "skills"
    dest.mkdir(parents=True)
    (repo / "skills" / "tracking-work").mkdir(parents=True, exist_ok=True)
    (dest / "tracking-work").symlink_to(repo / "skills" / "tracking-work")

    removed, _ = uninstall_skills(target_root=home, owner_root=repo)
    assert not (dest / "tracking-work").is_symlink()
    assert len(removed) == 1


def test_dry_run_changes_nothing(tmp_path, repo):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    install_skills(skills_src=repo / "skills", target_root=home, home=home)

    removed, _ = uninstall_skills(
        target_root=home, owner_root=repo, dry_run=True)
    assert len(removed) == 2
    assert (home / ".claude" / "skills" / "cortex-kb").is_symlink()
