"""Locating resources bundled with cortex.

`skills/` and `commands/` ship inside the wheel, where force-include places
the repo-root trees at `cortex/skills/` and `cortex/commands/`. A
run-from-clone invocation reads them from the repo root instead. Resolving
through here keeps that difference in one place, rather than each caller
counting directory levels up from its own __file__ and breaking whenever the
layout gains one.
"""
from __future__ import annotations

from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent


def bundled_dir(name: str) -> Path:
    """The bundled `name` tree: the packaged copy if present, else the repo's."""
    packaged = _PACKAGE_ROOT / name
    if packaged.is_dir():
        return packaged
    # src/cortex/ -> parents[1] is the repo root, which is where skills/ lives.
    return _PACKAGE_ROOT.parents[1] / name


def skills_dir() -> Path:
    return bundled_dir("skills")


def commands_dir() -> Path:
    return bundled_dir("commands")
