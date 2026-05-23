"""Shared fixtures for work_viz tests."""
from pathlib import Path
import pytest


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def workspaces_root(tmp_path):
    """Copy the canonical fixture tree into a tmp dir and yield the path."""
    import shutil
    root = tmp_path / "workspaces"
    root.mkdir()
    for sub in ("demo-ws", "other-ws", "kb-ghosts-ws", "authored-ws"):
        shutil.copytree(FIXTURES / sub, root / sub)
    return root
