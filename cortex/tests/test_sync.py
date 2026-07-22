import subprocess
from pathlib import Path

import pytest

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


def _second_clone(tmp_path, name="other"):
    """A second working clone of the same origin, for creating divergence."""
    other = tmp_path / name
    _git("clone", str(tmp_path / "origin.git"), str(other), cwd=tmp_path)
    _git("config", "user.email", "o@e", cwd=other)
    _git("config", "user.name", "o", cwd=other)
    return other


def _commit_push(wd, relpath, text, msg):
    p = wd / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    _git("add", "-A", cwd=wd)
    _git("commit", "-q", "-m", msg, cwd=wd)
    _git("push", "-q", "origin", "HEAD", cwd=wd)


def test_push_retries_after_non_fast_forward(tmp_path):
    wd = _mk_store_with_origin(tmp_path)
    other = _second_clone(tmp_path)
    _commit_push(other, "OTHER.md", "hi", "other advance")   # origin moves ahead
    (wd / "NEW.md").write_text("local")                      # non-conflicting local change
    rc = sync.push("track: local", home=tmp_path)
    assert rc == 0
    log = subprocess.run(["git", "log", "--oneline"], cwd=wd,
                         capture_output=True, text=True).stdout
    assert "track: local" in log and "other advance" in log   # rebased + retried


def test_pull_summary_conflict_autoresolves_to_upstream(tmp_path, capsys):
    wd = _mk_store_with_origin(tmp_path)
    other = _second_clone(tmp_path)
    _commit_push(other, "SUMMARY.md", "UPSTREAM", "up summary")
    (wd / "SUMMARY.md").write_text("LOCAL")
    _git("add", "-A", cwd=wd)
    _git("commit", "-q", "-m", "local summary", cwd=wd)
    rc = sync.pull(home=tmp_path, summary_conflict="resolve")
    assert rc == 0
    assert (wd / "SUMMARY.md").read_text() == "UPSTREAM"          # upstream side taken
    assert not (wd / ".git" / "rebase-merge").exists()           # rebase finished
    assert not (wd / ".git" / "rebase-apply").exists()
    assert "regenerate-needed" in capsys.readouterr().out


def test_pull_task_conflict_surfaces_exit_2(tmp_path):
    wd = _mk_store_with_origin(tmp_path)
    other = _second_clone(tmp_path)
    _commit_push(other, "tasks/x.md", "UP", "up task")
    (wd / "tasks").mkdir()
    (wd / "tasks" / "x.md").write_text("LOCAL")
    _git("add", "-A", cwd=wd)
    _git("commit", "-q", "-m", "local task", cwd=wd)
    rc = sync.pull(home=tmp_path, summary_conflict="resolve")
    assert rc == 2                                               # surfaced, not auto-resolved
    assert not (wd / ".git" / "rebase-merge").exists()          # rebase aborted


def test_setup_skip_writes_sentinel(tmp_path):
    assert sync.setup("skip", home=tmp_path) == 0
    assert (tmp_path / ".cortex" / ".sync-disabled").exists()


def test_setup_clone_refuses_nonempty_store(tmp_path):
    wd = tmp_path / ".cortex"
    wd.mkdir()
    (wd / "data").write_text("x")     # pre-existing content
    with pytest.raises(SystemExit):
        sync.setup("clone", home=tmp_path, url="https://example.com/x.git")
    assert (wd / "data").exists()     # not clobbered
