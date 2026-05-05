"""pytest fixtures for work-viz tests."""
from pathlib import Path
import pytest


@pytest.fixture
def fixtures_root() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_work"


@pytest.fixture
def workspaces_root(fixtures_root: Path) -> Path:
    return fixtures_root / "workspaces"
