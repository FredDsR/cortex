from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from cortex.paths import skills_dir

from .links import install_skills, uninstall_skills

DISTRIBUTION_NAME = "cortex-tracking"


def packaged_skills_dir() -> Path:
    """The skills tree as shipped, wherever it lives.

    Resolution belongs to cortex.paths, which prefers the packaged copy inside
    the wheel and falls back to the repo root for a run-from-clone.
    """
    return skills_dir()


def _owner_root() -> Path:
    """The tree our symlinks point into, for uninstall ownership checks."""
    return packaged_skills_dir().parent


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def _target_root(project: str | None) -> Path:
    return Path(project).resolve() if project else _home()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cortex")
    sub = p.add_subparsers(dest="verb", required=True)

    ins = sub.add_parser("install-skills",
                         help="Link cortex's skills into each harness")
    ins.add_argument("--project", nargs="?", const=".", default=None,
                     help="Install into <path>/.<harness>/skills/")

    rm = sub.add_parser("uninstall-skills",
                        help="Remove cortex's skills from each harness")
    rm.add_argument("--project", nargs="?", const=".", default=None)
    rm.add_argument("--dry-run", action="store_true")

    up = sub.add_parser("upgrade",
                        help="Upgrade the engine and relink the skills")
    up.add_argument("--to", default=None,
                    help="Pin an exact version instead of the newest")
    return p


def _do_upgrade(to: str | None) -> int:
    """Upgrade the engine, then relink skills so the two cannot skew."""
    spec = f"{DISTRIBUTION_NAME}=={to}" if to else DISTRIBUTION_NAME
    if shutil.which("uv"):
        cmd = ["uv", "tool", "install", "--force", spec]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", spec]
    print(f"cortex upgrade: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("cortex upgrade: engine upgrade failed", file=sys.stderr)
        return result.returncode
    home = _home()
    for line in install_skills(skills_src=packaged_skills_dir(),
                               target_root=home, home=home):
        print(line)
    return 0


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)

    if args.verb == "install-skills":
        for line in install_skills(skills_src=packaged_skills_dir(),
                                   target_root=_target_root(args.project),
                                   home=_home()):
            print(line)
        return 0

    if args.verb == "uninstall-skills":
        removed, kept = uninstall_skills(
            target_root=_target_root(args.project),
            owner_root=_owner_root(), dry_run=args.dry_run)
        for path in removed:
            print(f"removed {path}")
        for path in kept:
            print(f"kept    {path} (not ours)")
        return 0

    return _do_upgrade(args.to)
