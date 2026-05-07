from pathlib import Path
from work_viz.parser import parse_workspace, parse_world, _parse_typed_relations, _parse_mentions
from work_viz.model import (
    STATUS_IN_PROGRESS, STATUS_OPEN, STATUS_BLOCKED, STATUS_RESOLVED,
    Edge,
)


def test_enumerates_sessions_and_tasks(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    assert ws.slug == "demo"
    assert ws.has_meta is True
    sessions = [s for s in ws.sessions if not s.archived]
    assert len(sessions) == 1
    sess = sessions[0]
    assert sess.slug == "feature-x"
    assert len(sess.tasks) == 3
    slugs = {t.slug for t in sess.tasks}
    assert slugs == {"task-foo", "task-bar", "task-baz"}


def test_captures_task_body(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    foo = next(t for t in sess.tasks if t.slug == "task-foo")
    assert "The foo task." in foo.body
    assert foo.body.startswith("# Foo")


def test_captures_summary_text(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    assert "# Session: Feature X" in sess.summary_text
    assert sess.summary_meta.get("Github") == "example/demo"


def test_inline_fields_parsed(workspaces_root: Path):
    """task-foo uses YAML frontmatter; parser must surface Title-Case keys."""
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    foo = next(t for t in sess.tasks if t.slug == "task-foo")
    assert foo.inline_fields["Status"] == "In Progress"
    assert foo.inline_fields["Started"] == "2026-04-20"


def test_frontmatter_keys_normalized_to_title_case(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    foo = next(t for t in sess.tasks if t.slug == "task-foo")
    assert "status" not in foo.inline_fields  # raw lowercase keys not exposed
    assert foo.body.startswith("# Foo")  # frontmatter stripped from body


def test_legacy_bold_pair_still_parsed(workspaces_root: Path):
    """task-bar uses the legacy bold-pair format. Must keep working."""
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    bar = next(t for t in sess.tasks if t.slug == "task-bar")
    assert bar.inline_fields["Status"] == "Open"


def test_status_from_summary_headings(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    by_slug = {t.slug: t.status for t in sess.tasks}
    assert by_slug["task-foo"] == STATUS_IN_PROGRESS
    assert by_slug["task-bar"] == STATUS_OPEN
    assert by_slug["task-baz"] == STATUS_BLOCKED


def test_blocked_by_extracted(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    bar = next(t for t in sess.tasks if t.slug == "task-bar")
    baz = next(t for t in sess.tasks if t.slug == "task-baz")
    assert bar.blocked_by == ["task-foo"]
    assert baz.blocked_by == ["task-foo", "task-bar"]


def test_active_agent_count(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    assert sess.active_agent_count == 2


def test_workspace_active_session_slugs(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    assert ws.active_session_slugs == ["feature-x"]


def test_archived_sessions_present(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    archived = [s for s in ws.sessions if s.archived]
    assert len(archived) == 1
    s = archived[0]
    assert s.slug == "old-feature"
    assert s.archived is True


def test_session_parse_populates_edges_out(workspaces_root: Path):
    """task-foo.md declares blocked/related/follows relations; edges_out must reflect them."""
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    foo = next(t for t in sess.tasks if t.slug == "task-foo")

    blocked_edge = Edge(source="task-foo", target="task-baz", kind="blocked", resolved=False)
    related_edge = Edge(source="task-foo", target="task-bar", kind="related", resolved=False)
    follows_edge = Edge(source="task-foo", target="task-bar", kind="follows", resolved=False)

    assert blocked_edge in foo.edges_out, f"blocked edge missing; got {foo.edges_out}"
    assert related_edge in foo.edges_out, f"related edge missing; got {foo.edges_out}"
    assert follows_edge in foo.edges_out, f"follows edge missing; got {foo.edges_out}"


# ---------------------------------------------------------------------------
# _parse_typed_relations unit tests
# ---------------------------------------------------------------------------

def test_typed_relations_body_blocked_by():
    body = "Some prose.\nBlocked by: [task-foo], [task-bar]\nMore prose."
    rels = _parse_typed_relations(body, {})
    assert ("blocked", "task-foo") in rels
    assert ("blocked", "task-bar") in rels


def test_typed_relations_body_related_to():
    body = "Related to: [task-foo]"
    rels = _parse_typed_relations(body, {})
    assert rels == [("related", "task-foo")]


def test_typed_relations_body_follows():
    body = "Follows: task-bar"
    rels = _parse_typed_relations(body, {})
    assert rels == [("follows", "task-bar")]


def test_typed_relations_multiple_targets_per_line():
    body = "Related to: [task-a], [task-b], task-c"
    rels = _parse_typed_relations(body, {})
    assert ("related", "task-a") in rels
    assert ("related", "task-b") in rels
    assert ("related", "task-c") in rels


def test_typed_relations_frontmatter_list():
    fm = {"blocked_by": "[task-foo, task-bar]", "related_to": "[task-baz]"}
    rels = _parse_typed_relations("", fm)
    assert ("blocked", "task-foo") in rels
    assert ("blocked", "task-bar") in rels
    assert ("related", "task-baz") in rels


def test_typed_relations_dedup_body_and_frontmatter():
    body = "Blocked by: [task-foo]"
    fm = {"blocked_by": "[task-foo]"}
    rels = _parse_typed_relations(body, fm)
    assert rels.count(("blocked", "task-foo")) == 1


def test_typed_relations_bare_slug_form():
    body = "Related to: task-bar"
    rels = _parse_typed_relations(body, {})
    assert ("related", "task-bar") == rels[0]


def test_typed_relations_bold_label_variant():
    """Bold markdown around the label should still match."""
    body = "**Blocked by:** [task-x]"
    rels = _parse_typed_relations(body, {})
    assert ("blocked", "task-x") in rels


def test_typed_relations_case_insensitive():
    """Labels should match regardless of case."""
    body = "RELATED TO: task-z"
    rels = _parse_typed_relations(body, {})
    assert ("related", "task-z") in rels


def test_typed_relations_cross_ws_path():
    """Slash-separated references up to two slashes are accepted."""
    body = "Follows: feature-x/task-foo\nRelated to: demo/feature-x/task-bar"
    rels = _parse_typed_relations(body, {})
    assert ("follows", "feature-x/task-foo") in rels
    assert ("related", "demo/feature-x/task-bar") in rels


def test_typed_relations_frontmatter_single_string():
    """A single bare value (not in brackets) treated as one-element list."""
    fm = {"follows": "task-alpha"}
    rels = _parse_typed_relations("", fm)
    assert ("follows", "task-alpha") in rels


def test_typed_relations_order_frontmatter_first():
    """Frontmatter entries come before body entries in the result list."""
    body = "Related to: task-body"
    fm = {"related_to": "[task-fm]"}
    rels = _parse_typed_relations(body, fm)
    kinds = [r for r in rels if r[0] == "related"]
    assert kinds[0] == ("related", "task-fm")
    assert kinds[1] == ("related", "task-body")


# ---------------------------------------------------------------------------
# _parse_mentions unit tests
# ---------------------------------------------------------------------------

def test_mentions_bare_slug_in_prose():
    """Bare task-* reference in prose is picked up as a mention."""
    body = "We tracked this in task-bar earlier."
    mentions = _parse_mentions(body, [], "task-other")
    assert "task-bar" in mentions


def test_mentions_link_form():
    """Bracketed [task-slug] form in prose is picked up as a mention."""
    body = "See [task-foo] for context."
    mentions = _parse_mentions(body, [], "task-other")
    assert "task-foo" in mentions


def test_mentions_dedup_with_typed_relations():
    """A slug already captured as a typed relation is excluded from mentions."""
    body = "Blocked by: [task-foo]\nSee task-foo for background."
    typed_targets = ["task-foo"]
    mentions = _parse_mentions(body, typed_targets, "task-other")
    assert "task-foo" not in mentions
    assert mentions == []


def test_mentions_self_reference_skipped():
    """Self-references (source_slug matches target) are excluded from mentions."""
    body = "This task (task-foo) is self-referential."
    mentions = _parse_mentions(body, [], "task-foo")
    assert "task-foo" not in mentions
    assert mentions == []


def test_mentions_code_fence_excluded():
    """References inside triple-backtick fences are not picked up as mentions."""
    body = "Some prose.\n```\ntask-bar is inside a fence\n```\nEnd."
    mentions = _parse_mentions(body, [], "task-other")
    assert "task-bar" not in mentions


def test_mentions_repeat_dedup():
    """The same slug appearing multiple times in prose appears only once in output."""
    body = "See task-bar and also task-bar again."
    mentions = _parse_mentions(body, [], "task-other")
    assert mentions.count("task-bar") == 1


def test_mentions_dedup_typed_target_in_plain_prose():
    """Slug already in typed_targets is excluded even when it appears in plain prose, not on a typed-relation line."""
    body = "We discussed task-foo in a previous meeting."
    mentions = _parse_mentions(body, ["task-foo"], "task-other")
    assert mentions == []


def test_mentions_require_task_prefix_on_leaf():
    """Bracketed forms whose leaf segment isn't task- prefixed are not mentions.
    Without this, regex character classes like `[i]` in code-fence-adjacent prose
    pollute the graph with phantom mentions to non-existent tasks."""
    body = "Pattern matches `[i]` in regex; see [a-z0-9-]+ for the syntax."
    mentions = _parse_mentions(body, [], "task-other")
    assert mentions == []


def test_mentions_bracket_with_session_prefix_still_requires_task():
    """`[session/foo]` (no task- prefix on leaf) is also not a mention."""
    body = "Refer to [other-session/foo] for context."
    mentions = _parse_mentions(body, [], "task-other")
    assert mentions == []
    body2 = "Refer to [other-session/task-foo] for context."
    mentions2 = _parse_mentions(body2, [], "task-other")
    assert "other-session/task-foo" in mentions2


# ---------------------------------------------------------------------------
# parse_world tests
# ---------------------------------------------------------------------------

def test_world_local_edge_resolution(workspaces_root: Path):
    """Local edge: task-foo's blocked edge resolves to demo/feature-x/task-baz."""
    world = parse_world(workspaces_root)
    demo_ws = next(ws for ws in world.workspaces if ws.slug == "demo")
    sess = next(s for s in demo_ws.sessions if s.slug == "feature-x")
    foo = next(t for t in sess.tasks if t.slug == "task-foo")
    blocked_edges = [e for e in foo.edges_out if e.kind == "blocked"]
    assert len(blocked_edges) == 1
    e = blocked_edges[0]
    assert e.target == "demo/feature-x/task-baz"
    assert e.resolved is True


def test_world_cross_ws_demo_to_other(workspaces_root: Path):
    """task-foo has a resolved related edge pointing to other/sister/task-pinned."""
    world = parse_world(workspaces_root)
    demo_ws = next(ws for ws in world.workspaces if ws.slug == "demo")
    sess = next(s for s in demo_ws.sessions if s.slug == "feature-x")
    foo = next(t for t in sess.tasks if t.slug == "task-foo")
    cross_edges = [
        e for e in foo.edges_out
        if e.kind == "related" and e.target == "other/sister/task-pinned"
    ]
    assert len(cross_edges) == 1
    assert cross_edges[0].resolved is True


def test_world_cross_ws_other_to_demo(workspaces_root: Path):
    """task-pinned has a resolved related edge pointing to demo/feature-x/task-foo."""
    world = parse_world(workspaces_root)
    other_ws = next(ws for ws in world.workspaces if ws.slug == "other")
    sess = next(s for s in other_ws.sessions if s.slug == "sister")
    pinned = next(t for t in sess.tasks if t.slug == "task-pinned")
    cross_edges = [
        e for e in pinned.edges_out
        if e.kind == "related" and e.target == "demo/feature-x/task-foo"
    ]
    assert len(cross_edges) == 1
    assert cross_edges[0].resolved is True


def test_world_ghost_target(tmp_path: Path):
    """An edge pointing at a nonexistent task produces a ghost entry."""
    # Build a minimal workspace fixture in tmp_path
    ws_dir = tmp_path / "workspaces" / "tmpws" / "sessions" / "s1" / "tasks"
    ws_dir.mkdir(parents=True)
    # SUMMARY.md for session s1
    summary = tmp_path / "workspaces" / "tmpws" / "sessions" / "s1" / "SUMMARY.md"
    summary.write_text(
        "---\nslug: s1\nstatus: Active\n---\n\n# Session\n\n## Tasks\n\n### Open\n\n- task-ghost\n",
        encoding="utf-8",
    )
    # task that references a nonexistent target
    task_file = ws_dir / "task-ghost.md"
    task_file.write_text(
        "---\nstatus: Open\n---\n\n# Ghost\n\nBlocked by: [task-missing]\n",
        encoding="utf-8",
    )
    world = parse_world(tmp_path / "workspaces")
    assert len(world.workspaces) == 1
    assert "tmpws/s1/task-missing" in world.ghosts
    ghost_ws = world.workspaces[0]
    ghost_sess = next(s for s in ghost_ws.sessions if s.slug == "s1")
    ghost_task = next(t for t in ghost_sess.tasks if t.slug == "task-ghost")
    unresolved = [e for e in ghost_task.edges_out if e.kind == "blocked"]
    assert len(unresolved) == 1
    assert unresolved[0].resolved is False
    assert unresolved[0].target == "tmpws/s1/task-missing"
