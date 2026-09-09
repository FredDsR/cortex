"""Paths shared by the test suite.

Importable (unlike a conftest), so tests needing the fixture tree get one
definition of where it lives instead of each recomputing it.
"""
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TESTS_ROOT.parent

FIXTURES = TESTS_ROOT / "fixtures"

# Skill-owned scripts under test. These are not part of the cortex package.
SKILL_SCRIPTS = REPO_ROOT / "skills"
