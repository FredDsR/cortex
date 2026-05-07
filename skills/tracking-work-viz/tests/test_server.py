import json
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from work_viz.server import VizServer


@pytest.fixture
def writable_workspaces(tmp_path: Path, workspaces_root: Path) -> Path:
    dest = tmp_path / "workspaces"
    shutil.copytree(workspaces_root, dest)
    return dest


def _start_server(workspaces_root: Path, slug: str) -> VizServer:
    srv = VizServer(workspaces_root=workspaces_root, slug=slug, port=0)
    srv.start()
    return srv


def test_server_serves_data_json(writable_workspaces: Path):
    """/data.json emits the Workspace shape (slug/sessions/...) plus available_workspaces."""
    srv = _start_server(writable_workspaces, "demo")
    try:
        url = f"http://127.0.0.1:{srv.port}/data.json"
        with urllib.request.urlopen(url, timeout=5) as r:
            payload = json.loads(r.read())
        # Workspace shape
        assert "slug" in payload
        assert payload["slug"] == "demo"
        assert "sessions" in payload
        # Injected cross-WS list
        assert "available_workspaces" in payload
        assert "demo" in payload["available_workspaces"]
    finally:
        srv.stop()


def test_server_emits_sse_change_on_file_modification(writable_workspaces: Path):
    srv = _start_server(writable_workspaces, "demo")
    received = []
    stop_evt = threading.Event()

    def listen():
        url = f"http://127.0.0.1:{srv.port}/events"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                for raw in r:
                    if stop_evt.is_set():
                        break
                    line = raw.decode("utf-8").strip()
                    if line.startswith("data: "):
                        received.append(line[len("data: "):])
                        if len(received) >= 1:
                            break
        except Exception:
            pass

    t = threading.Thread(target=listen, daemon=True)
    t.start()
    time.sleep(0.3)  # let SSE handshake settle

    # Touch a task file
    task_path = writable_workspaces / "demo" / "sessions" / "feature-x" / "tasks" / "task-foo.md"
    task_path.write_text(task_path.read_text() + "\n<!-- touched -->\n")

    t.join(timeout=5)
    stop_evt.set()
    srv.stop()

    assert any("change" in m for m in received), f"received={received}"


from work_viz.server import DashboardServer


def test_dashboard_server_serves_dashboard(writable_workspaces: Path, tmp_path: Path):
    viz_out = tmp_path / "viz"
    srv = DashboardServer(workspaces_root=writable_workspaces, port=0, viz_dir=viz_out)
    srv.start()
    try:
        url = f"http://127.0.0.1:{srv.port}/dashboard.html"
        with urllib.request.urlopen(url, timeout=5) as r:
            body = r.read().decode("utf-8")
        assert "@@DATA@@" not in body
        assert '"slug": "demo"' in body or '"slug":"demo"' in body
        # Fetching index should also work and trigger regeneration.
        url2 = f"http://127.0.0.1:{srv.port}/"
        with urllib.request.urlopen(url2, timeout=5) as r:
            assert r.status == 200
        # Per-workspace page is generated on demand.
        url3 = f"http://127.0.0.1:{srv.port}/demo.html"
        with urllib.request.urlopen(url3, timeout=5) as r:
            demo_body = r.read().decode("utf-8")
        assert '"slug": "demo"' in demo_body or '"slug":"demo"' in demo_body
    finally:
        srv.stop()


def test_dashboard_server_blocks_path_traversal(writable_workspaces: Path, tmp_path: Path):
    viz_out = tmp_path / "viz"
    srv = DashboardServer(workspaces_root=writable_workspaces, port=0, viz_dir=viz_out)
    srv.start()
    try:
        url = f"http://127.0.0.1:{srv.port}/vendor/../../etc/passwd"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                assert False, f"expected 404, got {r.status}"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        srv.stop()


def test_dashboard_server_injects_hot_reload_script(writable_workspaces: Path, tmp_path: Path):
    viz_out = tmp_path / "viz"
    srv = DashboardServer(workspaces_root=writable_workspaces, port=0, viz_dir=viz_out)
    srv.start()
    try:
        url = f"http://127.0.0.1:{srv.port}/dashboard.html"
        with urllib.request.urlopen(url, timeout=5) as r:
            body = r.read().decode("utf-8")
        assert 'new EventSource("/events")' in body
        assert "location.reload()" in body
    finally:
        srv.stop()


def test_viz_server_inlines_cy_data(workspaces_root: Path, tmp_path: Path):
    """/  response must embed a non-null __CY_DATA__ so the watch-mode graph is populated at page load."""
    srv = VizServer(workspaces_root=workspaces_root, slug="demo", port=0, runtime_dir=tmp_path)
    srv.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.port}/", timeout=5) as r:
            html = r.read().decode("utf-8")
        assert "window.__CY_DATA__ = null" not in html
        assert '"modes"' in html  # cy_data was inlined as JSON
    finally:
        srv.stop()


def test_dashboard_server_emits_sse_change_on_workspace_modification(writable_workspaces: Path, tmp_path: Path):
    viz_out = tmp_path / "viz"
    srv = DashboardServer(workspaces_root=writable_workspaces, port=0, viz_dir=viz_out)
    srv.start()
    received = []
    stop_evt = threading.Event()

    def listen():
        url = f"http://127.0.0.1:{srv.port}/events"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                for raw in r:
                    if stop_evt.is_set():
                        break
                    line = raw.decode("utf-8").strip()
                    if line.startswith("data: "):
                        received.append(line[len("data: "):])
                        if len(received) >= 1:
                            break
        except Exception:
            pass

    t = threading.Thread(target=listen, daemon=True)
    t.start()
    time.sleep(0.3)

    # Touch a file under the workspace root
    task_path = writable_workspaces / "demo" / "sessions" / "feature-x" / "tasks" / "task-foo.md"
    task_path.write_text(task_path.read_text() + "\n<!-- touched -->\n")

    t.join(timeout=5)
    stop_evt.set()
    srv.stop()

    assert any("change" in m for m in received), f"received={received}"
