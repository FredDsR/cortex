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


# --- containment: workspace/session tokens are agent-supplied (issue #33) ---

# Traversal first, then tokens that are not a single path segment at all.
# The empty string is deliberately absent: it means "not supplied" and selects
# the auto-discovery branch, so it would pass this test for the wrong reason.
BAD_TOKENS = ["..", ".", "demo/../../..", "../../../tmp", "a/b", "/etc",
              "a\\b", "ws\n", "ws\0x"]


@pytest.mark.parametrize("token", BAD_TOKENS)
def test_resolve_workspace_rejects_non_segment_tokens(tmp_path, token):
    _mk_ws(tmp_path, "demo")
    with pytest.raises(store.StoreError, match="invalid workspace name"):
        store.resolve_workspace(token, home=tmp_path, cwd=tmp_path)


@pytest.mark.parametrize("token", BAD_TOKENS)
def test_resolve_session_rejects_non_segment_tokens(tmp_path, token):
    ws = _mk_ws(tmp_path, "demo", sessions=["s1"])
    with pytest.raises(store.StoreError, match="invalid session name"):
        store.resolve_session(ws, token)


def test_absolute_workspace_token_does_not_win_over_the_root(tmp_path):
    # `root / "/etc"` is `/etc` in pathlib: an absolute token discards the root
    # entirely, so it escapes even without a single `..`.
    _mk_ws(tmp_path, "demo")
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(store.StoreError):
        store.resolve_workspace(str(outside), home=tmp_path, cwd=tmp_path)


def test_resolve_workspace_rejects_symlink_pointing_outside_root(tmp_path):
    # Passes _validate_name; only the containment gate catches this.
    _mk_ws(tmp_path, "demo")
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / ".cortex" / "workspaces" / "sneaky"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(store.StoreError, match="escapes the store root"):
        store.resolve_workspace("sneaky", home=tmp_path, cwd=tmp_path)


def test_resolve_session_rejects_symlink_pointing_outside_root(tmp_path):
    ws = _mk_ws(tmp_path, "demo", sessions=["s1"])
    outside = tmp_path / "outside"
    outside.mkdir()
    (ws / "sessions" / "sneaky").symlink_to(outside, target_is_directory=True)
    with pytest.raises(store.StoreError, match="escapes the store root"):
        store.resolve_session(ws, "sneaky")


def test_valid_names_are_still_accepted(tmp_path):
    # Real slugs come from a git remote (`owner-repo`) or, in the fallback,
    # `basename "$cwd"` -- so anything a directory can be named has to keep
    # working: dots and dashes in any position, underscores, uppercase, spaces.
    for name in ["FredDsR-cortex", "ws_a", "v1.2", "a", "Repo.Name-2",
                 "_scratch", ".dotfiles", "-x", "My Project", "..hidden"]:
        ws = _mk_ws(tmp_path, name, sessions=[name])
        assert store.resolve_workspace(name, home=tmp_path, cwd=tmp_path) == ws
        assert store.resolve_session(ws, name) == name


def test_symlink_inside_root_is_allowed(tmp_path):
    # Containment is about escaping, not about symlinks as such.
    real = tmp_path / ".cortex" / "workspaces" / "real"
    (real / "sessions").mkdir(parents=True)
    link = tmp_path / ".cortex" / "workspaces" / "alias"
    link.symlink_to(real, target_is_directory=True)
    assert store.resolve_workspace("alias", home=tmp_path, cwd=tmp_path) == link


def test_active_pointer_content_cannot_escape_the_store(tmp_path):
    # The pointer file is agent-written too, and callers join the returned name
    # onto `<ws>/sessions/`, so an unvalidated pointer was the same escape as a
    # `--session` token: kb would have written to /tmp/pwn/workbench/.
    ws = _mk_ws(tmp_path, "demo", sessions=["s1"])
    (ws / ".active.testid").write_text("../../../../../../tmp/pwn\n")
    with pytest.raises(store.StoreError, match="invalid session name"):
        store.resolve_session(ws, "")


def test_blank_active_pointer_means_no_active_session(tmp_path):
    ws = _mk_ws(tmp_path, "demo", sessions=["s1"])
    (ws / ".active.testid").write_text("\n")
    with pytest.raises(store.StoreError, match="no active session"):
        store.resolve_session(ws, "")


def test_resolve_scope_all_lists_every_workspace(tmp_path):
    root = tmp_path / ".cortex" / "workspaces"
    for name in ("wsb", "wsa"):
        (root / name).mkdir(parents=True)
    (root / "loose.txt").write_text("not a workspace\n")
    parsed, names = store.resolve_scope("all", home=tmp_path, cwd=tmp_path)
    assert parsed == root
    assert names == ["wsa", "wsb"]          # sorted, files excluded


def test_resolve_scope_all_on_empty_home(tmp_path):
    parsed, names = store.resolve_scope("all", home=tmp_path, cwd=tmp_path)
    assert parsed == tmp_path / ".cortex" / "workspaces"
    assert names == []


def test_resolve_scope_explicit_returns_parent_and_one_name(tmp_path):
    root = tmp_path / ".cortex" / "workspaces"
    (root / "wsa").mkdir(parents=True)
    parsed, names = store.resolve_scope("wsa", home=tmp_path, cwd=tmp_path)
    assert parsed == root                    # the parent, so siblings stay parseable
    assert names == ["wsa"]


def test_resolve_scope_local_store_root_is_the_repo(tmp_path):
    # A repo-local store is `<repo>/.cortex`, so its parent is the repo itself.
    repo = tmp_path / "proj"
    (repo / ".cortex").mkdir(parents=True)
    parsed, names = store.resolve_scope("", home=tmp_path, cwd=repo)
    assert parsed == repo
    assert names == [".cortex"]
