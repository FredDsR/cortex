from cortex import parser, query
from cortex.model import DocId


def _world(workspaces_root):
    return parser.parse_world(workspaces_root, include_archive=True)


def test_outgoing_links_grouped_and_resolved(workspaces_root):
    world = _world(workspaces_root)
    target = DocId(kind="task", workspace="demo-ws", session="alpha", slug="task-a")
    res = query.neighbors(world, target)
    got = {(n.kind, n.address) for n in res.outgoing}
    assert ("blocked", "task-b") in got                       # same session -> bare slug
    assert ("related", "beta/task-c") in got                  # same workspace, other session
    assert ("follows", "other-ws/zeta/task-z") in got         # other workspace


def test_backlinks_include_container_and_authored(workspaces_root):
    world = _world(workspaces_root)
    # task-b is blocked-by target of task-a, and contained by session alpha.
    target = DocId(kind="task", workspace="demo-ws", session="alpha", slug="task-b")
    res = query.neighbors(world, target)
    kinds = {(n.kind, n.doc_id.canonical()) for n in res.backlinks}
    assert ("blocked", "demo-ws/alpha/task/task-a") in kinds
    assert ("contains", "demo-ws/alpha/") in kinds
    # session backlink is non-linkable: address falls back to canonical, no crash
    contains = [n for n in res.backlinks if n.kind == "contains"][0]
    assert contains.address == "demo-ws/alpha/"


def test_ghost_references_listed(workspaces_root):
    world = _world(workspaces_root)
    target = DocId(kind="task", workspace="kb-ghosts-ws", session="solo", slug="task-ghosted")
    res = query.neighbors(world, target)
    ghosts = {(g.kind, g.raw_target) for g in res.ghosts}
    assert ("related", "knowledge/missing-note") in ghosts
    assert ("related", "workbench/draft-x") in ghosts
    assert res.outgoing == []   # neither resolved to a real doc


def test_resolved_ref_to_missing_doc_is_ghost(workspaces_root):
    world = _world(workspaces_root)
    # task-b mentions [knowledge/architecture]; demo-ws/knowledge has no such file.
    target = DocId(kind="task", workspace="demo-ws", session="alpha", slug="task-b")
    res = query.neighbors(world, target)
    assert ("mentions", "knowledge/architecture") in {(g.kind, g.raw_target) for g in res.ghosts}


def test_summary_prefers_description_then_title(workspaces_root):
    world = _world(workspaces_root)
    # authored-ws/knowledge/typed has a description; it should be the summary.
    doc = world.docs["authored-ws/knowledge/typed"]
    assert query._summary(doc) == "a one-line description"
    # task-a has no description -> title "Task a"
    assert query._summary(world.docs["demo-ws/alpha/task/task-a"]) == "Task a"


def test_find_by_slug_narrowing_and_ambiguity(workspaces_root):
    world = _world(workspaces_root)
    assert len(query.find_by_slug(world, "task-a")) == 1
    assert query.find_by_slug(world, "task-a")[0].id.workspace == "demo-ws"
    assert query.find_by_slug(world, "no-such-slug") == []
    # narrowing by workspace filters
    assert query.find_by_slug(world, "task-z", workspace="demo-ws") == []
    assert len(query.find_by_slug(world, "task-z", workspace="other-ws")) == 1


def test_checkbox_marker_is_not_a_ghost(tmp_path):
    # A GFM checked checkbox `- [x]` must not surface as a `mentions x` ghost.
    ws = tmp_path / "workspaces" / "wsz" / "sessions" / "s1" / "tasks"
    ws.mkdir(parents=True)
    (ws.parent / "SUMMARY.md").write_text("---\nslug: s1\nstatus: Active\n---\n\n# s1\n")
    (ws / "cb.md").write_text(
        "---\nslug: cb\nstatus: Open\n---\n\n# Cb\n\n- [x] done\n- [ ] todo\n")
    world = parser.parse_world(tmp_path / "workspaces", include_archive=True)
    target = DocId(kind="task", workspace="wsz", session="s1", slug="cb")
    res = query.neighbors(world, target)
    assert "x" not in {g.raw_target for g in res.ghosts}


def test_self_reference_not_listed_as_neighbor(tmp_path):
    ws = tmp_path / "workspaces" / "wsz" / "sessions" / "s1" / "tasks"
    ws.mkdir(parents=True)
    (ws.parent / "SUMMARY.md").write_text("---\nslug: s1\nstatus: Active\n---\n\n# s1\n")
    # body mentions its own bare slug -> a self-edge would otherwise form
    (ws / "task-loop.md").write_text(
        "---\nslug: task-loop\nstatus: Open\n---\n\n# Loop\n\nsee task-loop again\n")
    world = parser.parse_world(tmp_path / "workspaces", include_archive=True)
    target = DocId(kind="task", workspace="wsz", session="s1", slug="task-loop")
    res = query.neighbors(world, target)
    canon = target.canonical()
    assert canon not in {n.doc_id.canonical() for n in res.outgoing}
    assert canon not in {n.doc_id.canonical() for n in res.backlinks}


def test_find_by_slug_kind_narrowing(tmp_path):
    ws = tmp_path / "workspaces" / "wsz"
    (ws / "knowledge").mkdir(parents=True)
    (ws / "sessions" / "s1" / "tasks").mkdir(parents=True)
    (ws / "sessions" / "s1" / "SUMMARY.md").write_text(
        "---\nslug: s1\nstatus: Active\n---\n\n# s1\n")
    (ws / "knowledge" / "dup.md").write_text("---\nslug: dup\n---\n\n# K\n")
    (ws / "sessions" / "s1" / "tasks" / "dup.md").write_text(
        "---\nslug: dup\nstatus: Open\n---\n\n# T\n")
    world = parser.parse_world(tmp_path / "workspaces", include_archive=True)
    assert len(query.find_by_slug(world, "dup")) == 2                      # ambiguous
    assert len(query.find_by_slug(world, "dup", kind="task")) == 1         # kind narrows
    assert query.find_by_slug(world, "dup", kind="knowledge")[0].id.kind == "knowledge"


def test_max_caps_and_reports_total(workspaces_root):
    world = _world(workspaces_root)
    target = DocId(kind="task", workspace="demo-ws", session="alpha", slug="task-a")
    res = query.neighbors(world, target, max=2)
    assert len(res.outgoing) == 2
    assert res.outgoing_total == 3   # blocked + related + follows
