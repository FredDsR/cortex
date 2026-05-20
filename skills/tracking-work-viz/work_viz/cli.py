"""Command-line entry point for work-viz."""
from __future__ import annotations
import argparse
import socketserver
import sys
import threading
from pathlib import Path

from .parser import parse_world
from .generator import build as build_world
from .serve import serve, _make_server


DEFAULT_WORKSPACES_ROOT = Path.home() / ".work" / "workspaces"
DEFAULT_OUT_DIR = Path.home() / ".cache" / "work-viz" / "out"


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work-viz",
                                 description="Static browser-based viewer for ~/.work/.")
    sub = p.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="Build the static site.")
    b.add_argument("workspaces_root", nargs="?", default=str(DEFAULT_WORKSPACES_ROOT))
    b.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)

    s = sub.add_parser("serve", help="Serve a built out/ directory.")
    s.add_argument("out_dir", nargs="?", type=Path, default=DEFAULT_OUT_DIR)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=0)
    s.add_argument("--no-open", action="store_true")

    return p


def _start_server_for_test(out_dir: Path, port: int) -> tuple[socketserver.TCPServer, threading.Thread]:
    """Helper used by tests; not part of the public CLI."""
    httpd = _make_server(Path(out_dir), "127.0.0.1", port)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, t


def main(argv: list[str] | None = None) -> int:
    parser = _build_argparser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        # default: build into the cache dir, then serve
        world = parse_world(DEFAULT_WORKSPACES_ROOT, include_archive=True)
        build_world(world, DEFAULT_OUT_DIR)
        serve(DEFAULT_OUT_DIR)
        return 0
    if args.cmd == "build":
        world = parse_world(Path(args.workspaces_root), include_archive=True)
        build_world(world, args.out)
        print(f"work-viz build: wrote {args.out}")
        return 0
    if args.cmd == "serve":
        serve(args.out_dir, host=args.host, port=args.port,
              open_browser=not args.no_open)
        return 0
    parser.error(f"unknown subcommand: {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
