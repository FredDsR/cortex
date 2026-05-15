"""Smoke test for the static file server."""
import threading
import urllib.request
import socket
from pathlib import Path
import pytest
from work_viz.parser import parse_world
from work_viz.generator import build
from work_viz.serve import _make_server


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_serves_root_html(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    port = _free_port()
    httpd = _make_server(out, "127.0.0.1", port)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html", timeout=2)
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "__SCOPE__" in body
    finally:
        httpd.shutdown()


def test_serves_copied_md(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    port = _free_port()
    httpd = _make_server(out, "127.0.0.1", port)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/workspaces/demo-ws/sessions/alpha/tasks/task-a.md", timeout=2)
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "task-a" in body.lower()
    finally:
        httpd.shutdown()
