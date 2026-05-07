"""Command-line entry point for work-viz."""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .parser import parse_world


DEFAULT_WORKSPACES_ROOT = Path.home() / ".work" / "workspaces"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work-viz", description="Browser-based viewer for ~/.work/.")
    p.add_argument("workspace", nargs="?",
                   help="Workspace slug to render. Use 'serve' for the dashboard server, 'all' for one-shot dashboard.")
    p.add_argument("--workspace", dest="workspace_flag", help="Set to 'all' for the cross-workspace dashboard.")
    p.add_argument("--watch", action="store_true", help="Per-workspace watch mode (local server + SSE).")
    p.add_argument("--serve", action="store_true",
                   help="Start a local HTTP server fronting ~/.work/viz/ (dashboard + per-workspace pages). "
                        "Bypasses snap-Firefox file:// restrictions.")
    p.add_argument("--json", dest="emit_json", action="store_true", help="Print parsed model JSON to stdout.")
    p.add_argument("--workspaces-root", type=Path, default=DEFAULT_WORKSPACES_ROOT,
                   help="Override the workspaces root (defaults to ~/.work/workspaces).")
    p.add_argument("--out-dir", type=Path, default=None,
                   help="Override the output directory for generated HTML (defaults to ~/.work/viz). "
                        "Vendor JS/CSS must already be present in <out-dir>/vendor/ for the page to render.")
    p.add_argument("--port", type=int, default=0, help="Server port (0 picks 8765..8775 for watch, 8800..8810 for serve).")
    p.add_argument("--no-open", action="store_true", help="Server modes: don't auto-open the browser.")
    return p


def main(argv: list | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Resolve output dir: explicit --out-dir wins, otherwise fall back to the generator default.
    from .generator import DEFAULT_OUT_DIR as _DEFAULT_OUT
    out_dir = args.out_dir if args.out_dir is not None else _DEFAULT_OUT

    # `serve` either via positional `serve` or via --serve flag
    if args.serve or args.workspace == "serve":
        from .server import DashboardServer
        from .generator import generate_dashboard
        # Generate fresh content before serving so the dashboard reflects current state.
        generate_dashboard(args.workspaces_root, out_dir=out_dir)
        srv = DashboardServer(workspaces_root=args.workspaces_root, port=args.port, viz_dir=out_dir)
        srv.start()
        url = f"http://127.0.0.1:{srv.port}/dashboard.html"
        print(f"work-viz serve: dashboard at {url}")
        print("(regenerates on every page request; Ctrl-C to stop)")
        if not args.no_open:
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception:
                pass
        try:
            while True:
                import time as _t
                _t.sleep(60)
        except KeyboardInterrupt:
            print("stopping")
        finally:
            srv.stop()
        return 0

    if args.workspace_flag == "all" or args.workspace == "all":
        from .generator import generate_dashboard
        out = generate_dashboard(args.workspaces_root, out_dir=out_dir)
        print(out)
        return 0

    if not args.workspace:
        parser.error("workspace slug is required (or use --workspace=all, or `serve`)")

    if args.emit_json:
        world = parse_world(args.workspaces_root)
        json.dump(asdict(world), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.watch:
        from .server import VizServer
        srv = VizServer(workspaces_root=args.workspaces_root, slug=args.workspace,
                         port=args.port, runtime_dir=out_dir)
        srv.start()
        url = f"http://127.0.0.1:{srv.port}/"
        print(f"work-viz watch: serving {url}")
        if not args.no_open:
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception:
                pass
        try:
            while True:
                import time as _t
                _t.sleep(60)
        except KeyboardInterrupt:
            print("stopping")
        finally:
            srv.stop()
        return 0

    from .generator import generate_one_shot
    out = generate_one_shot(args.workspaces_root, args.workspace, out_dir=out_dir)
    print(out)
    return 0
