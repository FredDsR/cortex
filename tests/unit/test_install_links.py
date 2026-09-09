import pytest

from cortex.install.links import install_skills, is_owned_link, link_skill


@pytest.fixture
def skills_src(tmp_path):
    """Two real skills and one husk with no SKILL.md."""
    src = tmp_path / "repo" / "skills"
    for name in ("cortex-tracking", "cortex-kb"):
        d = src / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    husk = src / "cortex-renamed"
    husk.mkdir(parents=True)
    (husk / "__pycache__").mkdir()
    return src


def test_link_skill_creates_a_symlink(tmp_path, skills_src):
    dest = tmp_path / "dest" / "cortex-kb"
    dest.parent.mkdir(parents=True)
    assert link_skill(skills_src / "cortex-kb", dest) == "installed"
    assert dest.is_symlink()
    assert dest.resolve() == (skills_src / "cortex-kb").resolve()


def test_link_skill_relinks_an_existing_symlink(tmp_path, skills_src):
    dest = tmp_path / "dest" / "cortex-kb"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(tmp_path / "somewhere-else")
    assert link_skill(skills_src / "cortex-kb", dest) == "relinked"
    assert dest.resolve() == (skills_src / "cortex-kb").resolve()


def test_link_skill_backs_up_a_real_directory(tmp_path, skills_src):
    dest = tmp_path / "dest" / "cortex-kb"
    dest.mkdir(parents=True)
    (dest / "mine.md").write_text("do not delete me")
    assert link_skill(skills_src / "cortex-kb", dest) == "replaced"
    assert dest.is_symlink()
    backups = list(dest.parent.glob("cortex-kb.bak.*"))
    assert len(backups) == 1
    assert (backups[0] / "mine.md").read_text() == "do not delete me"


def test_install_skills_skips_a_harness_whose_home_dir_is_absent(
        tmp_path, skills_src):
    home = tmp_path / "home"
    home.mkdir()
    log = install_skills(skills_src=skills_src, target_root=home, home=home)
    assert any("not present, skipping" in line for line in log)
    assert not (home / ".claude" / "skills").exists()


def test_install_skills_links_into_a_present_harness(tmp_path, skills_src):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    install_skills(skills_src=skills_src, target_root=home, home=home)
    dest = home / ".claude" / "skills"
    assert (dest / "cortex-tracking").is_symlink()
    assert (dest / "cortex-kb").is_symlink()


def test_install_skills_skips_a_directory_without_skill_md(
        tmp_path, skills_src):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    log = install_skills(skills_src=skills_src, target_root=home, home=home)
    assert not (home / ".claude" / "skills" / "cortex-renamed").exists()
    assert any("no SKILL.md" in line for line in log)


def test_install_skills_removes_stale_pre_rebrand_symlinks(
        tmp_path, skills_src):
    home = tmp_path / "home"
    dest = home / ".claude" / "skills"
    dest.mkdir(parents=True)
    stale = dest / "tracking-work"
    stale.symlink_to(tmp_path / "old-repo" / "tracking-work")
    install_skills(skills_src=skills_src, target_root=home, home=home)
    assert not stale.is_symlink()


def test_install_skills_never_writes_to_an_uninstall_only_harness(
        tmp_path, skills_src):
    home = tmp_path / "home"
    (home / ".gemini").mkdir(parents=True)
    install_skills(skills_src=skills_src, target_root=home, home=home)
    assert not (home / ".gemini" / "skills").exists()


def test_is_owned_link_only_accepts_symlinks_into_the_owner_root(tmp_path):
    owner = tmp_path / "repo"
    (owner / "skills" / "cortex-kb").mkdir(parents=True)
    mine = tmp_path / "mine"
    mine.symlink_to(owner / "skills" / "cortex-kb")
    theirs = tmp_path / "theirs"
    theirs.symlink_to(tmp_path / "elsewhere")
    real = tmp_path / "real"
    real.mkdir()
    assert is_owned_link(mine, owner) is True
    assert is_owned_link(theirs, owner) is False
    assert is_owned_link(real, owner) is False
