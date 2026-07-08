"""Integration tests for the live edit server."""
import json
import socket
import threading
import urllib.request
import urllib.error
import pytest
from work_viz.parser import parse_world
from work_viz.generator import build
from work_viz import edit_server


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out, workspaces_root=workspaces_root)
    port = _free_port()
    httpd = edit_server.make_edit_server(out, workspaces_root, "127.0.0.1", port)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"
    try:
        yield base, httpd
    finally:
        httpd.shutdown()


def _get(base, path):
    resp = urllib.request.urlopen(base + path, timeout=2)
    return resp.status, json.loads(resp.read().decode())


def _post(base, path, obj, token=None):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(base + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token is not None:
        req.add_header("X-Work-Viz-Token", token)
    resp = urllib.request.urlopen(req, timeout=3)
    return resp.status, json.loads(resp.read().decode())


def test_capabilities(live):
    base, httpd = live
    status, data = _get(base, "/api/capabilities")
    assert status == 200
    assert data["edit"] is True
    assert data["token"] == httpd.token


def test_source_editable_task(live):
    base, _ = live
    status, data = _get(base, "/api/source?id=demo-ws/alpha/task/task-a")
    assert status == 200
    assert data["editable"] is True
    assert "task-a" in data["content"].lower()
    assert len(data["hash"]) == 64


def test_source_non_editable_workspace(live):
    base, _ = live
    status, data = _get(base, "/api/source?id=demo-ws/")
    assert status == 200
    assert data["editable"] is False


def test_source_unknown_id_404(live):
    base, _ = live
    with pytest.raises(urllib.error.HTTPError) as ei:
        _get(base, "/api/source?id=demo-ws/alpha/task/nope")
    assert ei.value.code == 404


def test_static_file_still_served(live):
    base, _ = live
    resp = urllib.request.urlopen(base + "/index.html", timeout=2)
    assert resp.status == 200


def test_save_happy_path(live):
    base, httpd = live
    _, src = _get(base, "/api/source?id=demo-ws/alpha/task/task-a")
    new = src["content"] + "\n\nAppended line.\n"
    status, data = _post(base, "/api/save", {
        "id": "demo-ws/alpha/task/task-a", "content": new,
        "baseHash": src["hash"], "scope": "root", "scopeId": "/",
    }, token=httpd.token)
    assert status == 200
    assert "payload" in data and data["payload"]["scope"] == "root"
    copy = urllib.request.urlopen(
        base + "/workspaces/demo-ws/sessions/alpha/tasks/task-a.md", timeout=2
    ).read().decode()
    assert "Appended line." in copy


def test_save_stale_hash_409(live):
    base, httpd = live
    status = None
    try:
        _post(base, "/api/save", {
            "id": "demo-ws/alpha/task/task-a", "content": "x",
            "baseHash": "deadbeef", "scope": "root", "scopeId": "/",
        }, token=httpd.token)
    except urllib.error.HTTPError as e:
        status = e.code
        body = json.loads(e.read().decode())
        assert "currentContent" in body
    assert status == 409


def test_save_requires_token_403(live):
    base, _ = live
    with pytest.raises(urllib.error.HTTPError) as ei:
        _post(base, "/api/save", {
            "id": "demo-ws/alpha/task/task-a", "content": "x",
            "baseHash": "x", "scope": "root", "scopeId": "/",
        }, token=None)
    assert ei.value.code == 403


def test_save_non_editable_400(live):
    base, httpd = live
    with pytest.raises(urllib.error.HTTPError) as ei:
        _post(base, "/api/save", {
            "id": "demo-ws/", "content": "x", "baseHash": "x",
            "scope": "root", "scopeId": "/",
        }, token=httpd.token)
    assert ei.value.code == 400


def test_save_resolves_ghost_edge(live):
    base, httpd = live
    # task-a already blocks task-b in the fixture; add the reverse, which is a
    # genuinely new edge, and confirm it appears in the rebuilt payload.
    _, src = _get(base, "/api/source?id=demo-ws/alpha/task/task-b")
    new = src["content"] + "\n\nBlocked by: task-a\n"
    status, data = _post(base, "/api/save", {
        "id": "demo-ws/alpha/task/task-b", "content": new,
        "baseHash": src["hash"], "scope": "session", "scopeId": "demo-ws/alpha/",
    }, token=httpd.token)
    assert status == 200
    edges = data["payload"]["edges"]
    assert any(e["source"].endswith("task/task-b")
               and e["target"].endswith("task/task-a")
               and e["kind"] == "blocked" for e in edges)
