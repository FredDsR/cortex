from pathlib import Path
from work_viz.parser import parse_workspace
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
    assert sess.summary_meta.get("github") == "example/demo"


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
