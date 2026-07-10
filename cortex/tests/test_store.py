import pytest
from cortex import store


def _mk_ws(home, name, active=None, sessions=()):
    ws = home / ".work" / "workspaces" / name
    (ws / "sessions").mkdir(parents=True, exist_ok=True)
    for s in sessions:
        (ws / "sessions" / s).mkdir(parents=True, exist_ok=True)
    if active:
        (ws / ".active.testid").write_text(active + "\n")
    return ws


def test_resolve_workspace_explicit_found_and_missing(tmp_path):
    ws = _mk_ws(tmp_path, "ws-a")
    assert store.resolve_workspace("ws-a", home=tmp_path, cwd=tmp_path) == ws
    with pytest.raises(store.StoreError):
        store.resolve_workspace("nope", home=tmp_path, cwd=tmp_path)


def test_resolve_workspace_by_unique_active_pointer(tmp_path):
    ws = _mk_ws(tmp_path, "ws-a", active="s1", sessions=["s1"])
    _mk_ws(tmp_path, "ws-b")  # no active pointer
    assert store.resolve_workspace("", home=tmp_path, cwd=tmp_path) == ws


def test_resolve_workspace_ambiguous_active(tmp_path):
    _mk_ws(tmp_path, "ws-a", active="s1", sessions=["s1"])
    _mk_ws(tmp_path, "ws-b", active="s2", sessions=["s2"])
    with pytest.raises(store.StoreError):
        store.resolve_workspace("", home=tmp_path, cwd=tmp_path)


def test_resolve_workspace_none_active(tmp_path):
    _mk_ws(tmp_path, "ws-a")
    with pytest.raises(store.StoreError):
        store.resolve_workspace("", home=tmp_path, cwd=tmp_path)


def test_resolve_session_explicit_and_active_and_ambiguous(tmp_path):
    ws = _mk_ws(tmp_path, "ws-a", active="s1", sessions=["s1", "s2"])
    assert store.resolve_session(ws, "s2") == "s2"        # explicit, exists
    assert store.resolve_session(ws, "") == "s1"          # unique active
    with pytest.raises(store.StoreError):
        store.resolve_session(ws, "nope")                 # explicit, missing
    # two distinct active pointers -> ambiguous
    (ws / ".active.other").write_text("s2\n")
    with pytest.raises(store.StoreError):
        store.resolve_session(ws, "")


def test_find_local_store_walks_up_within_home(tmp_path):
    repo = tmp_path / "proj"
    (repo / ".work").mkdir(parents=True)
    deep = repo / "a" / "b"
    deep.mkdir(parents=True)
    assert store.find_local_store(deep, home=tmp_path) == repo / ".work"
    assert store.find_local_store(tmp_path, home=tmp_path) is None
