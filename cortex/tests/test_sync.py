import subprocess
from pathlib import Path

from cortex import sync


def _git(*a, cwd):
    subprocess.run(["git", *a], cwd=cwd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _mk_store_with_origin(tmp_path):
    """Bare origin + a working ~/.cortex clone with identity configured."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git("init", "--bare", "-b", "main", ".", cwd=origin)
    wd = tmp_path / ".cortex"
    _git("clone", str(origin), str(wd), cwd=tmp_path)
    _git("config", "user.email", "t@e", cwd=wd)
    _git("config", "user.name", "t", cwd=wd)
    # Seed an initial commit so origin has a branch to rebase onto (a real
    # store is never empty by the time push/pull run).
    (wd / ".gitkeep").write_text("")
    _git("add", "-A", cwd=wd)
    _git("commit", "-q", "-m", "init", cwd=wd)
    _git("push", "-q", "origin", "HEAD", cwd=wd)
    return wd


def test_is_enabled_false_when_store_missing(tmp_path):
    # No ~/.cortex on disk at all: must not raise, just report disabled.
    assert sync.is_enabled(tmp_path) is False
    assert sync.push("track: x", home=tmp_path) == 0
    assert sync.pull(home=tmp_path) == 0


def test_is_enabled_false_without_git(tmp_path):
    (tmp_path / ".cortex").mkdir()
    assert sync.is_enabled(tmp_path) is False


def test_is_enabled_false_with_sentinel(tmp_path):
    wd = tmp_path / ".cortex"
    wd.mkdir()
    (wd / ".sync-disabled").touch()
    assert sync.is_enabled(tmp_path) is False


def test_is_enabled_true_with_origin(tmp_path):
    _mk_store_with_origin(tmp_path)
    assert sync.is_enabled(tmp_path) is True


def test_push_noop_when_disabled(tmp_path):
    (tmp_path / ".cortex").mkdir()
    assert sync.push("track: x", home=tmp_path) == 0   # no-op, no crash


def test_push_commits_to_local_origin(tmp_path):
    wd = _mk_store_with_origin(tmp_path)
    (wd / "SUMMARY.md").write_text("hello")
    rc = sync.push("track: first", home=tmp_path)
    assert rc == 0
    log = subprocess.run(["git", "log", "--oneline"], cwd=wd,
                         capture_output=True, text=True).stdout
    assert "track: first" in log


def test_push_noop_when_nothing_staged(tmp_path):
    _mk_store_with_origin(tmp_path)
    assert sync.push("track: empty", home=tmp_path) == 0


def test_pull_clean_returns_zero(tmp_path):
    _mk_store_with_origin(tmp_path)
    assert sync.pull(home=tmp_path) == 0


def test_pull_noop_when_disabled(tmp_path):
    (tmp_path / ".cortex").mkdir()
    assert sync.pull(home=tmp_path) == 0
