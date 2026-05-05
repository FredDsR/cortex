from pathlib import Path
from work_viz.parser import parse_workspace


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
