import pytest
from cortex import store


def _mk_ws(home, name, active=None, sessions=(), meta_cwd=None):
    ws = home / ".cortex" / "workspaces" / name
    (ws / "sessions").mkdir(parents=True, exist_ok=True)
    for s in sessions:
        (ws / "sessions" / s).mkdir(parents=True, exist_ok=True)
    if active:
        (ws / ".active.testid").write_text(active + "\n")
    if meta_cwd is not None:
        (ws / ".meta").write_text(
            f"cwd: {meta_cwd}\nremote: \nsource: meta\nupdated: 2026-07-28\n")
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


def test_resolve_workspace_by_meta_cwd(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    ws = _mk_ws(tmp_path, "ws-a", meta_cwd=proj)
    _mk_ws(tmp_path, "ws-b", meta_cwd=tmp_path / "other")
    assert store.resolve_workspace("", home=tmp_path, cwd=proj) == ws


def test_meta_cwd_wins_over_ambiguous_active_pointers(tmp_path):
    # The reported bug: unrelated workspaces holding stale .active.* pointers
    # made resolution ambiguous even when cwd named a workspace exactly.
    proj = tmp_path / "proj"
    proj.mkdir()
    ws = _mk_ws(tmp_path, "ws-a", meta_cwd=proj)
    _mk_ws(tmp_path, "ws-b", active="s1", sessions=["s1"])
    _mk_ws(tmp_path, "ws-c", active="s2", sessions=["s2"])
    assert store.resolve_workspace("", home=tmp_path, cwd=proj) == ws


def test_local_store_still_wins_over_meta_cwd(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".cortex").mkdir(parents=True)
    _mk_ws(tmp_path, "ws-a", meta_cwd=proj)
    assert store.resolve_workspace("", home=tmp_path, cwd=proj) == proj / ".cortex"


def test_explicit_workspace_still_wins_over_meta_cwd(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    _mk_ws(tmp_path, "ws-a", meta_cwd=proj)
    ws_b = _mk_ws(tmp_path, "ws-b")
    assert store.resolve_workspace("ws-b", home=tmp_path, cwd=proj) == ws_b


def test_non_matching_meta_falls_back_to_active_pointer(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    _mk_ws(tmp_path, "ws-a", meta_cwd=tmp_path / "elsewhere")
    ws_b = _mk_ws(tmp_path, "ws-b", active="s1", sessions=["s1"])
    assert store.resolve_workspace("", home=tmp_path, cwd=proj) == ws_b


def test_malformed_meta_is_ignored(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    bad = _mk_ws(tmp_path, "ws-a")
    (bad / ".meta").write_text("this is not: parseable\nno cwd key here\n")
    ws_b = _mk_ws(tmp_path, "ws-b", active="s1", sessions=["s1"])
    assert store.resolve_workspace("", home=tmp_path, cwd=proj) == ws_b


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
    (repo / ".cortex").mkdir(parents=True)
    deep = repo / "a" / "b"
    deep.mkdir(parents=True)
    assert store.find_local_store(deep, home=tmp_path) == repo / ".cortex"
    assert store.find_local_store(tmp_path, home=tmp_path) is None


def test_resolve_session_multiline_pointer_is_ambiguous(tmp_path):
    ws = _mk_ws(tmp_path, "ws-a", sessions=["s1", "s2"])
    (ws / ".active.testid").write_text("s1\ns2\n")   # one pointer, two lines
    with pytest.raises(store.StoreError):
        store.resolve_session(ws, "")
