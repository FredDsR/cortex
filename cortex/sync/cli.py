"""`cortex sync push` / `pull` / `status` / `setup`: argparse in, exit code out.

Thin by design. Everything these wrap already reports to stderr as it goes, so
there is little for this layer to print: `status` is the one command whose
output is its own.
"""
from __future__ import annotations
from pathlib import Path

from cortex.sync.repo import git, is_enabled, pull, push, work_dir
from cortex.sync.setup import interactive_setup, setup


def cmd_push(args) -> int:
    return push(args.message, home=Path.home())


def cmd_pull(args) -> int:
    return pull(home=Path.home(),
                summary_conflict=getattr(args, "summary_conflict", "resolve"))


def cmd_status(args) -> int:
    home = Path.home()
    if is_enabled(home):
        wd = work_dir(home)
        remote = git(["remote", "get-url", "origin"], cwd=wd, capture=True).stdout.strip()
        print(f"cortex-sync: enabled (origin: {remote})")
        return 0
    print("cortex-sync: not enabled")
    return 1


def cmd_setup(args) -> int:
    if getattr(args, "skip", False):
        return setup("skip", home=Path.home())
    if getattr(args, "clone", None):
        return setup("clone", home=Path.home(), url=args.clone)
    if getattr(args, "init", False):
        return setup("init", home=Path.home(), name=getattr(args, "name", None) or "work-tracking")
    # No flags: fall back to the interactive menu (matches the docs).
    return interactive_setup(Path.home())
