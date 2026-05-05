from work_viz.model import (
    Task, Session, Workspace,
    STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_BLOCKED, STATUS_RESOLVED, STATUS_UNKNOWN,
    ALL_STATUSES,
)


def test_task_defaults():
    t = Task(slug="task-foo")
    assert t.slug == "task-foo"
    assert t.body == ""
    assert t.inline_fields == {}
    assert t.blocked_by == []
    assert t.status == STATUS_UNKNOWN


def test_session_defaults():
    s = Session(slug="feature-x")
    assert s.tasks == []
    assert s.active_agent_count == 0
    assert s.archived is False


def test_workspace_defaults():
    w = Workspace(slug="demo")
    assert w.sessions == []
    assert w.has_meta is False


def test_status_constants_unique():
    assert len(set(ALL_STATUSES)) == 5
