import json
import shutil
import threading
import time
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
    srv = _start_server(writable_workspaces, "demo")
    try:
        url = f"http://127.0.0.1:{srv.port}/data.json"
        with urllib.request.urlopen(url, timeout=5) as r:
            payload = json.loads(r.read())
        assert payload["slug"] == "demo"
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
