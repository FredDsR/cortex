"""CLI smoke tests."""
import json
import subprocess
import sys
import threading
import urllib.request
import socket
from pathlib import Path
import pytest


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_cli_build(workspaces_root, tmp_path):
    out = tmp_path / "out"
    from work_viz.cli import main
    rc = main(["build", str(workspaces_root), "--out", str(out)])
    assert rc == 0
    assert (out / "index.html").is_file()
    assert (out / "workspaces" / "demo-ws" / "index.html").is_file()


def test_cli_serve_runs(workspaces_root, tmp_path):
    out = tmp_path / "out"
    from work_viz.cli import main, _start_server_for_test
    main(["build", str(workspaces_root), "--out", str(out)])
    port = _free_port()
    httpd, thread = _start_server_for_test(out, port)
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html", timeout=2)
        assert resp.status == 200
    finally:
        httpd.shutdown()
