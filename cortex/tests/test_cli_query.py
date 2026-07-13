import shutil
from pathlib import Path

from cortex import cli as cortex_cli


def _home_with_fixtures(tmp_path, monkeypatch):
    """Build $HOME/.work/workspaces/ from the shared fixture tree."""
    from cortex.conftest import FIXTURES
    root = tmp_path / ".work" / "workspaces"
    root.mkdir(parents=True)
    for sub in ("demo-ws", "other-ws", "kb-ghosts-ws", "authored-ws"):
        shutil.copytree(FIXTURES / sub, root / sub)
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_neighbors_prints_links(tmp_path, monkeypatch, capsys):
    _home_with_fixtures(tmp_path, monkeypatch)
    rc = cortex_cli.main(["query", "neighbors", "task-a"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "task-b" in out          # outgoing blocked
    assert "beta/task-c" in out     # outgoing related
    assert "Outgoing" in out and "Backlinks" in out


def test_neighbors_lists_ghosts(tmp_path, monkeypatch, capsys):
    _home_with_fixtures(tmp_path, monkeypatch)
    rc = cortex_cli.main(["query", "neighbors", "task-ghosted"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "knowledge/missing-note" in out
    assert "workbench/draft-x" in out


def test_unknown_slug_exits_1(tmp_path, monkeypatch, capsys):
    _home_with_fixtures(tmp_path, monkeypatch)
    rc = cortex_cli.main(["query", "neighbors", "no-such-slug"])
    assert rc == 1
    assert "no-such-slug" in capsys.readouterr().err


def test_ambiguous_slug_lists_candidates(tmp_path, monkeypatch, capsys):
    # Two workspaces with the same task slug -> ambiguous without narrowing.
    root = tmp_path / ".work" / "workspaces"
    for ws in ("wsx", "wsy"):
        d = root / ws / "sessions" / "s1" / "tasks"
        d.mkdir(parents=True)
        (root / ws / "sessions" / "s1" / "SUMMARY.md").write_text(
            "---\nslug: s1\nstatus: Active\n---\n\n# s1\n")
        (d / "dup.md").write_text("---\nslug: dup\nstatus: Open\n---\n\n# Dup\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = cortex_cli.main(["query", "neighbors", "dup"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "ambiguous" in err
    assert "wsx/s1/task/dup" in err and "wsy/s1/task/dup" in err
    # narrowing resolves it
    rc2 = cortex_cli.main(["query", "neighbors", "dup", "--workspace", "wsx"])
    assert rc2 == 0


def test_bad_max_exits_1(tmp_path, monkeypatch, capsys):
    _home_with_fixtures(tmp_path, monkeypatch)
    rc = cortex_cli.main(["query", "neighbors", "task-a", "--max", "notanint"])
    assert rc == 1


def test_query_registered_in_top_level_help(capsys):
    rc = cortex_cli.main(["--help"])
    assert rc == 0
    assert "query" in capsys.readouterr().out
