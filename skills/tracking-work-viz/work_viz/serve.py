"""Thin static file server over a generated out_dir, plus optional edit mode."""
from __future__ import annotations
import functools
import http.server
import json
import socketserver
import webbrowser
from pathlib import Path

from .generator import MANIFEST_NAME


def _make_server(out_dir: Path, host: str, port: int) -> socketserver.TCPServer:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out_dir))
    return socketserver.TCPServer((host, port), handler)


def _resolve_edit_root(out_dir: Path, override):
    if override:
        root = Path(override).resolve()
        if not root.is_dir():
            raise SystemExit(
                f"work-viz serve --edit: --workspaces-root not found: {root}")
        return root
    manifest = Path(out_dir) / MANIFEST_NAME
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        wr = data.get("workspacesRoot")
        if wr and Path(wr).is_dir():
            return Path(wr).resolve()
    raise SystemExit(
        "work-viz serve --edit: cannot locate source root; pass --workspaces-root")


def serve(out_dir: Path, host: str = "127.0.0.1", port: int = 0,
          open_browser: bool = True, edit: bool = False,
          workspaces_root=None) -> None:
    out_dir = Path(out_dir)
    if edit:
        from .edit_server import make_edit_server
        root = _resolve_edit_root(out_dir, workspaces_root)
        httpd = make_edit_server(out_dir, root, host, port, commit_on_save=True)
    else:
        httpd = _make_server(out_dir, host, port)
    actual_port = httpd.server_address[1]
    url = f"http://{host}:{actual_port}/index.html"
    mode = " (edit mode)" if edit else ""
    print(f"work-viz serve{mode}: {url}")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("stopping")
    finally:
        httpd.shutdown()
