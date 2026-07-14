import json

from cortex import cli, inject
from pathlib import Path


def _enable(kbhome, ws="ws-a"):
    (kbhome / ".work/workspaces" / ws / ".inject-enabled").write_text("on\n")


def _mk_knowledge(kbhome, slug, typ, desc, ws="ws-a"):
    kd = kbhome / ".work/workspaces" / ws / "knowledge"
    kd.mkdir(parents=True, exist_ok=True)
    (kd / f"{slug}.md").write_text(
        f"---\ntype: {typ}\nauthor: agent\ncreated: 2026-01-01\n"
        f"updated: 2026-01-01\ndescription: {desc}\n---\n\nbody\n")


def _mk_workbench(kbhome, slug, desc, sess="sess-a", ws="ws-a"):
    wd = kbhome / ".work/workspaces" / ws / "sessions" / sess / "workbench"
    wd.mkdir(parents=True, exist_ok=True)
    (wd / f"{slug}.md").write_text(
        f"---\nauthor: agent\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        f"description: {desc}\n---\n\nbody\n")


def test_here_empty_when_sentinel_absent(kbhome, capsys):
    _mk_knowledge(kbhome, "api-ver", "Decision", "why we pin v2")
    assert cli.main(["inject", "here", "--workspace", "ws-a"]) == 0
    assert capsys.readouterr().out == ""


def test_here_empty_when_workspace_unresolved(kbhome, capsys):
    assert cli.main(["inject", "here", "--workspace", "nope"]) == 0
    assert capsys.readouterr().out == ""


def _mk_task(kbhome, slug, status, title, sess="sess-a", ws="ws-a"):
    td = kbhome / ".work/workspaces" / ws / "sessions" / sess / "tasks"
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{slug}.md").write_text(
        f"---\nslug: {slug}\nstatus: {status}\nsession: {sess}\n---\n\n# {title}\n\nbody\n")


def test_here_renders_knowledge_and_workbench_when_enabled(kbhome, capsys):
    _enable(kbhome)
    _mk_knowledge(kbhome, "api-ver", "Decision", "why we pin v2")
    _mk_workbench(kbhome, "pr-draft", "draft PR description")
    assert cli.main(["inject", "here", "--workspace", "ws-a", "--session", "sess-a"]) == 0
    out = capsys.readouterr().out
    assert out.startswith('<tracking-work-index workspace="ws-a" session="sess-a">')
    assert "## knowledge" in out
    assert "api-ver [Decision] - why we pin v2" in out
    assert "## workbench (sess-a)" in out
    assert "pr-draft - draft PR description" in out
    assert out.rstrip().endswith("</tracking-work-index>")


def test_here_open_tasks_section(kbhome, capsys):
    _enable(kbhome)
    _mk_task(kbhome, "task-b-open", "Open", "Do the docs")
    _mk_task(kbhome, "task-a-wip", "In Progress", "Wire the hook")
    _mk_task(kbhome, "task-done", "Resolved", "Already merged")
    assert cli.main(["inject", "here", "--workspace", "ws-a", "--session", "sess-a"]) == 0
    out = capsys.readouterr().out
    assert "## open tasks" in out
    tasks = [ln for ln in out.splitlines() if ln.startswith("[")]
    assert tasks == ["[In Progress] task-a-wip - Wire the hook",
                     "[Open] task-b-open - Do the docs"]
    assert "task-done" not in out           # Resolved excluded


def test_here_no_open_tasks_section_when_none(kbhome, capsys):
    _enable(kbhome)
    _mk_task(kbhome, "task-done", "Resolved", "Already merged")
    cli.main(["inject", "here", "--workspace", "ws-a", "--session", "sess-a"])
    assert "## open tasks" not in capsys.readouterr().out


def test_here_byte_ceiling_truncates(kbhome, capsys, monkeypatch):
    _enable(kbhome)
    for i in range(50):
        _mk_knowledge(kbhome, f"doc-{i:03d}", "Reference",
                      "x" * 60 + f" number {i}")
    monkeypatch.setenv("CORTEX_INJECT_MAX_BYTES", "500")
    cli.main(["inject", "here", "--workspace", "ws-a"])
    out = capsys.readouterr().out
    assert len(out.encode("utf-8")) <= 700          # ceiling + tag/notice slack
    assert "truncated" in out
    assert out.rstrip().endswith("</tracking-work-index>")


def test_here_silent_on_corrupt_file(kbhome, capsys, monkeypatch):
    _enable(kbhome)
    kd = kbhome / ".work/workspaces/ws-a/knowledge"
    kd.mkdir(parents=True, exist_ok=True)
    (kd / "bad.md").write_bytes(b"\xff\xfe not utf8 \x00")

    def boom(*a, **k):
        raise ValueError("corrupt")
    monkeypatch.setattr("cortex.inject.kb._render_section", boom)
    assert cli.main(["inject", "here", "--workspace", "ws-a"]) == 0
    assert capsys.readouterr().out == ""


def test_here_claude_code_envelope(kbhome, capsys):
    _enable(kbhome)
    _mk_knowledge(kbhome, "api-ver", "Decision", "why we pin v2")
    cli.main(["inject", "here", "--workspace", "ws-a", "--format", "claude-code"])
    payload = json.loads(capsys.readouterr().out)
    hso = payload["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart"
    assert "api-ver [Decision] - why we pin v2" in hso["additionalContext"]


def test_here_claude_code_empty_when_gated_off(kbhome, capsys):
    # No sentinel -> empty stdout even in claude-code format.
    cli.main(["inject", "here", "--workspace", "ws-a", "--format", "claude-code"])
    assert capsys.readouterr().out == ""
