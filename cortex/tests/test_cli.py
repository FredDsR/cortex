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
    from cortex.viz.cli import main
    rc = main(["build", str(workspaces_root), "--out", str(out)])
    assert rc == 0
    assert (out / "index.html").is_file()
    assert (out / "workspaces" / "demo-ws" / "index.html").is_file()


def test_cli_serve_runs(workspaces_root, tmp_path):
    out = tmp_path / "out"
    from cortex.viz.cli import main, _start_server_for_test
    main(["build", str(workspaces_root), "--out", str(out)])
    port = _free_port()
    httpd, thread = _start_server_for_test(out, port)
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html", timeout=2)
        assert resp.status == 200
    finally:
        httpd.shutdown()


def test_serve_edit_exposes_capabilities(workspaces_root, tmp_path):
    import json as _json
    out = tmp_path / "out"
    from cortex.viz.cli import main
    main(["build", str(workspaces_root), "--out", str(out)])
    from cortex.viz import edit_server
    port = _free_port()
    httpd = edit_server.make_edit_server(out, workspaces_root, "127.0.0.1", port)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/capabilities", timeout=2)
        assert _json.loads(resp.read().decode())["edit"] is True
    finally:
        httpd.shutdown()


def test_plain_serve_has_no_api(workspaces_root, tmp_path):
    import urllib.error
    out = tmp_path / "out"
    from cortex.viz.cli import main, _start_server_for_test
    main(["build", str(workspaces_root), "--out", str(out)])
    port = _free_port()
    httpd, thread = _start_server_for_test(out, port)
    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/capabilities", timeout=2)
            assert False, "static server should not serve the API"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        httpd.shutdown()


def test_serve_edit_resolves_root_from_manifest(workspaces_root, tmp_path):
    out = tmp_path / "out"
    from cortex.viz.cli import main
    main(["build", str(workspaces_root), "--out", str(out)])
    from cortex.viz.serve import _resolve_edit_root
    assert _resolve_edit_root(out, None) == workspaces_root.resolve()
