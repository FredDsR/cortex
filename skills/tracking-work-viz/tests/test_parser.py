from pathlib import Path
from work_viz.parser import parse_workspace, _parse_typed_relations, _parse_mentions
from work_viz.model import (
    STATUS_IN_PROGRESS, STATUS_OPEN, STATUS_BLOCKED, STATUS_RESOLVED,
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
