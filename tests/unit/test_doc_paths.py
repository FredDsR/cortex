"""Prose docs describe behavior; they never name the module implementing it.

A cited path is a claim that goes stale the moment anything moves, and it made
a safe mechanical refactor look expensive purely because of doc drift. The
guarantee is the contract, not the file.
"""
import re

from support import REPO_ROOT

# A backticked path to a Python module, with or without the src/ prefix.
IMPL_PATH = re.compile(r"`((?:src/)?cortex/[A-Za-z0-9_/]+\.py)`")

# Contributor docs may name a genuine extension point. Everything else may not.
CONTRIBUTOR_DOCS = {"CONTRIBUTING.md"}

SKIP_PREFIXES = (".git/", ".venv/", "docs/superpowers/", "node_modules/",
                 "tests/e2e/node_modules/")


def _tracked_markdown():
    for path in REPO_ROOT.rglob("*.md"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith(SKIP_PREFIXES):
            continue
        yield rel, path


def test_no_implementation_paths_in_user_docs():
    offenders = []
    for rel, path in _tracked_markdown():
        if rel in CONTRIBUTOR_DOCS:
            continue
        for match in IMPL_PATH.finditer(path.read_text(encoding="utf-8")):
            offenders.append(f"{rel}: {match.group(1)}")
    assert offenders == [], (
        "implementation paths cited in prose docs:\n  " + "\n  ".join(offenders))


def test_paths_cited_in_contributor_docs_exist():
    missing = []
    for name in CONTRIBUTOR_DOCS:
        doc = REPO_ROOT / name
        if not doc.is_file():
            continue
        for match in IMPL_PATH.finditer(doc.read_text(encoding="utf-8")):
            if not (REPO_ROOT / match.group(1)).exists():
                missing.append(f"{name}: {match.group(1)}")
    assert missing == [], (
        "contributor docs cite paths that do not exist:\n  "
        + "\n  ".join(missing))
