"""Command-line entry point for work-viz."""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .parser import parse_workspace


DEFAULT_WORKSPACES_ROOT = Path.home() / ".work" / "workspaces"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work-viz", description="Browser-based viewer for ~/.work/.")
    p.add_argument("workspace", nargs="?", help="Workspace slug to render. Omit with --workspace=all.")
    p.add_argument("--workspace", dest="workspace_flag", help="Set to 'all' for the cross-workspace dashboard.")
    p.add_argument("--watch", action="store_true", help="Run in watch mode (local server + SSE).")
    p.add_argument("--json", dest="emit_json", action="store_true", help="Print parsed model JSON to stdout.")
    p.add_argument("--workspaces-root", type=Path, default=DEFAULT_WORKSPACES_ROOT,
                   help="Override the workspaces root (defaults to ~/.work/workspaces).")
    p.add_argument("--port", type=int, default=0, help="Watch-mode port (0 picks 8765..8775).")
    p.add_argument("--no-open", action="store_true", help="Watch mode: don't auto-open the browser.")
    return p


def main(argv: list | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.workspace_flag == "all" or args.workspace == "all":
        # Dashboard mode is wired in Task 12.
        print("dashboard mode not yet implemented", file=sys.stderr)
        return 2

    if not args.workspace:
        parser.error("workspace slug is required (or use --workspace=all)")

    if args.emit_json:
        ws = parse_workspace(args.workspaces_root, args.workspace)
        json.dump(asdict(ws), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.watch:
        # Wired in Task 11.
        print("watch mode not yet implemented", file=sys.stderr)
        return 2

    from .generator import generate_one_shot
    out = generate_one_shot(args.workspaces_root, args.workspace)
    print(out)
    return 0
