import pytest

from support import FIXTURES


@pytest.fixture
def kbhome(tmp_path, monkeypatch):
    """A temp HOME with ~/.cortex/workspaces/ws-a + an active session sess-a
    (mirrors the bash tests' make_test_home)."""
    home = tmp_path
    ws = home / ".cortex" / "workspaces" / "ws-a"
    (ws / "sessions" / "sess-a" / "workbench").mkdir(parents=True)
    (ws / "sessions" / "sess-a" / "tasks").mkdir()
    (ws / ".active.testid").write_text("sess-a\n")
    (ws / "sessions" / "sess-a" / "SUMMARY.md").write_text(
        "---\nslug: sess-a\nstatus: Active\n---\n\n# sess-a\n")
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def workspaces_root(tmp_path):
    """Copy the canonical fixture tree into a tmp dir and yield the path."""
    import shutil
    root = tmp_path / "workspaces"
    root.mkdir()
    for sub in ("demo-ws", "other-ws", "kb-ghosts-ws", "authored-ws"):
        shutil.copytree(FIXTURES / sub, root / sub)
    return root
