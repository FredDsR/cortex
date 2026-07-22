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


def test_conflict_only_when_new_holds_data(tmp_path):
    home = tmp_path
    (home / ".work" / "workspaces" / "ws").mkdir(parents=True)
    (home / ".cortex" / "workspaces" / "existing").mkdir(parents=True)  # real data
    rep = migrate(home, write=True)
    assert rep["action"] == "conflict"
    assert (home / ".work").exists()          # nothing destroyed on conflict


def test_merges_into_install_scaffold(tmp_path):
    # install.sh creates ~/.cortex/bin before the user can run migrate-store;
    # that bin-only scaffold must NOT block the merge (the F1 regression).
    home = tmp_path
    (home / ".work" / "workspaces" / "ws").mkdir(parents=True)
    (home / ".work" / "workspaces" / "ws" / "SUMMARY.md").write_text("x")
    (home / ".cortex" / "bin").mkdir(parents=True)
    (home / ".cortex" / "bin" / "cortex").write_text("#!/bin/sh\n")  # fresh install bin
    rep = migrate(home, write=True)
    assert rep["action"] == "moved"
    assert (home / ".cortex" / "workspaces" / "ws" / "SUMMARY.md").read_text() == "x"
    assert (home / ".cortex" / "bin" / "cortex").exists()   # fresh bin kept
    assert not (home / ".work").exists()


def test_empty_new_dir_merges(tmp_path):
    home = tmp_path
    (home / ".work" / "workspaces" / "ws").mkdir(parents=True)
    (home / ".cortex").mkdir()                # empty dir, not a real store
    assert migrate(home, write=True)["action"] == "moved"
    assert (home / ".cortex" / "workspaces" / "ws").is_dir()


def test_noop_when_no_old_store(tmp_path):
    assert migrate(tmp_path, write=True)["action"] == "noop"
