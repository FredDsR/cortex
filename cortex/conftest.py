import sys
from pathlib import Path

import pytest

# Ensure the repo root (parent of the cortex package) is importable so
# `import cortex.frontmatter` works regardless of pytest's invocation dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


@pytest.fixture
def kbhome(tmp_path, monkeypatch):
    """A temp HOME with ~/.work/workspaces/ws-a + an active session sess-a
    (mirrors the bash tests' make_test_home)."""
    home = tmp_path
    ws = home / ".work" / "workspaces" / "ws-a"
    (ws / "sessions" / "sess-a" / "workbench").mkdir(parents=True)
    (ws / "sessions" / "sess-a" / "tasks").mkdir()
    (ws / ".active.testid").write_text("sess-a\n")
    (ws / "sessions" / "sess-a" / "SUMMARY.md").write_text(
        "---\nslug: sess-a\nstatus: Active\n---\n\n# sess-a\n")
    monkeypatch.setenv("HOME", str(home))
    return home
