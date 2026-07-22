from pathlib import Path
from cortex.migrate_store import migrate


def test_dry_run_reports_move_without_touching_disk(tmp_path):
    home = tmp_path
    (home / ".work" / "workspaces" / "ws").mkdir(parents=True)
    rep = migrate(home, write=False)
    assert rep["action"] == "moved"
    assert (home / ".work").exists()          # dry-run must not move
    assert not (home / ".cortex").exists()


def test_write_moves_store_and_is_idempotent(tmp_path):
    home = tmp_path
    (home / ".work" / "workspaces" / "ws").mkdir(parents=True)
    (home / ".work" / "workspaces" / "ws" / "SUMMARY.md").write_text("x")
    r1 = migrate(home, write=True)
    assert r1["action"] == "moved"
    assert (home / ".cortex" / "workspaces" / "ws" / "SUMMARY.md").read_text() == "x"
    assert not (home / ".work").exists()
    r2 = migrate(home, write=True)            # idempotent
    assert r2["action"] == "noop"


def test_conflict_when_both_exist(tmp_path):
    home = tmp_path
    (home / ".work").mkdir()
    (home / ".cortex").mkdir()
    rep = migrate(home, write=True)
    assert rep["action"] == "conflict"
    assert (home / ".work").exists()          # nothing destroyed on conflict


def test_noop_when_no_old_store(tmp_path):
    assert migrate(tmp_path, write=True)["action"] == "noop"
