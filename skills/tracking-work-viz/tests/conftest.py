"""Shared fixtures for work_viz tests."""
import sys
from pathlib import Path
import pytest

# tests/ -> tracking-work-viz/ -> skills/ -> repo root, so the transitional
# work_viz re-export shims can `import cortex.*` while this suite runs in place.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))


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
