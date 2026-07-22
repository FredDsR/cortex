import json

from cortex import cli, inject
from pathlib import Path


def _enable(kbhome, ws="ws-a"):
    (kbhome / ".cortex/workspaces" / ws / ".inject-enabled").write_text("on\n")


def _mk_knowledge(kbhome, slug, typ, desc, ws="ws-a"):
    kd = kbhome / ".cortex/workspaces" / ws / "knowledge"
    kd.mkdir(parents=True, exist_ok=True)
    (kd / f"{slug}.md").write_text(
        f"---\ntype: {typ}\nauthor: agent\ncreated: 2026-01-01\n"
        f"updated: 2026-01-01\ndescription: {desc}\n---\n\nbody\n")


def _mk_workbench(kbhome, slug, desc, sess="sess-a", ws="ws-a"):
    wd = kbhome / ".cortex/workspaces" / ws / "sessions" / sess / "workbench"
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
    td = kbhome / ".cortex/workspaces" / ws / "sessions" / sess / "tasks"
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{slug}.md").write_text(
        f"---\nslug: {slug}\nstatus: {status}\nsession: {sess}\n---\n\n# {title}\n\nbody\n")


def test_here_renders_knowledge_and_workbench_when_enabled(kbhome, capsys):
    _enable(kbhome)
    _mk_knowledge(kbhome, "api-ver", "Decision", "why we pin v2")
    _mk_workbench(kbhome, "pr-draft", "draft PR description")
    assert cli.main(["inject", "here", "--workspace", "ws-a", "--session", "sess-a"]) == 0
    out = capsys.readouterr().out
    assert out.startswith('<cortex-index workspace="ws-a" session="sess-a">')
    assert "## knowledge" in out
    assert "api-ver [Decision] - why we pin v2" in out
    assert "## workbench (sess-a)" in out
    assert "pr-draft - draft PR description" in out
    assert out.rstrip().endswith("</cortex-index>")


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
    assert out.rstrip().endswith("</cortex-index>")


def test_here_silent_on_corrupt_file(kbhome, capsys, monkeypatch):
    _enable(kbhome)
    kd = kbhome / ".cortex/workspaces/ws-a/knowledge"
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


def _sentinel_path(kbhome, ws="ws-a"):
    return kbhome / ".cortex/workspaces" / ws / ".inject-enabled"


def test_enable_creates_sentinel(kbhome, capsys):
    assert cli.main(["inject", "enable", "--workspace", "ws-a"]) == 0
    assert _sentinel_path(kbhome).is_file()


def test_disable_removes_sentinel(kbhome):
    _enable(kbhome)
    assert cli.main(["inject", "disable", "--workspace", "ws-a"]) == 0
    assert not _sentinel_path(kbhome).is_file()


def test_disable_is_idempotent(kbhome):
    assert cli.main(["inject", "disable", "--workspace", "ws-a"]) == 0


def test_status_reports_sentinel(kbhome, capsys):
    _enable(kbhome)
    assert cli.main(["inject", "status", "--workspace", "ws-a"]) == 0
    out = capsys.readouterr().out
    assert "enabled" in out.lower()
    assert "ws-a" in out


def _settings(kbhome):
    return kbhome / ".claude/settings.json"


def test_wire_creates_entry_and_is_idempotent(kbhome):
    from cortex.inject import ClaudeCodeAdapter
    a = ClaudeCodeAdapter()
    assert a.wire(home=kbhome) is True
    assert a.is_wired(home=kbhome) is True
    data = json.loads(_settings(kbhome).read_text())
    entries = data["hooks"]["SessionStart"]
    ours = [e for e in entries
            if any("inject here --format=claude-code" in h["command"]
                   for h in e["hooks"])]
    assert len(ours) == 1
    assert ours[0]["matcher"] == "startup|clear|compact"
    # Second wire is a no-op.
    assert a.wire(home=kbhome) is False
    data2 = json.loads(_settings(kbhome).read_text())
    assert len(data2["hooks"]["SessionStart"]) == 1


def test_wire_preserves_unrelated_hooks(kbhome):
    from cortex.inject import ClaudeCodeAdapter
    _settings(kbhome).parent.mkdir(parents=True, exist_ok=True)
    _settings(kbhome).write_text(json.dumps({
        "hooks": {"SessionStart": [
            {"matcher": "startup",
             "hooks": [{"type": "command", "command": "echo other"}]}]},
        "model": "opus",
    }))
    a = ClaudeCodeAdapter()
    a.wire(home=kbhome)
    data = json.loads(_settings(kbhome).read_text())
    assert data["model"] == "opus"                       # untouched
    cmds = [h["command"] for e in data["hooks"]["SessionStart"] for h in e["hooks"]]
    assert "echo other" in cmds                           # preserved
    assert any("inject here --format=claude-code" in c for c in cmds)


def test_wire_refuses_to_clobber_malformed_settings(kbhome):
    from cortex.inject import ClaudeCodeAdapter
    from cortex.errors import CortexError
    import pytest
    _settings(kbhome).parent.mkdir(parents=True, exist_ok=True)
    original = '{ "model": "opus", trailing-comma-here, }'   # invalid JSON
    _settings(kbhome).write_text(original)
    a = ClaudeCodeAdapter()
    with pytest.raises(CortexError):
        a.wire(home=kbhome)
    assert _settings(kbhome).read_text() == original          # untouched, not clobbered


def test_wire_refuses_non_dict_hooks(kbhome):
    from cortex.inject import ClaudeCodeAdapter
    from cortex.errors import CortexError
    import pytest
    _settings(kbhome).parent.mkdir(parents=True, exist_ok=True)
    _settings(kbhome).write_text(json.dumps({"hooks": None}))
    a = ClaudeCodeAdapter()
    with pytest.raises(CortexError):
        a.wire(home=kbhome)


def test_status_survives_malformed_settings(kbhome, capsys):
    # is_wired must not crash status on a broken settings file.
    _enable(kbhome)
    (kbhome / ".claude").mkdir(parents=True, exist_ok=True)
    (kbhome / ".claude/settings.json").write_text("{ not json")
    assert cli.main(["inject", "status", "--workspace", "ws-a"]) == 0
    assert "wired hooks: (none)" in capsys.readouterr().out


def test_wire_command_uses_passed_home_when_cortex_not_on_path(kbhome, monkeypatch):
    from cortex.inject import ClaudeCodeAdapter
    monkeypatch.setattr("cortex.inject.shutil.which", lambda _: None)
    a = ClaudeCodeAdapter()
    a.wire(home=kbhome)
    cmd = json.loads(_settings(kbhome).read_text())["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert cmd.startswith(str(kbhome / ".cortex" / "bin" / "cortex"))


def test_here_bad_max_errors(kbhome):
    assert cli.main(["inject", "here", "--workspace", "ws-a", "--max", "abc"]) == 1


def test_here_byte_ceiling_strictly_bounded(kbhome, monkeypatch):
    _enable(kbhome)
    for i in range(50):
        _mk_knowledge(kbhome, f"doc-{i:03d}", "Reference", "y" * 60 + f" n{i}")
    monkeypatch.setenv("CORTEX_INJECT_MAX_BYTES", "600")
    from cortex import inject
    block = inject.render_block(home=kbhome, cwd=kbhome, workspace="ws-a",
                                session="", max_n=100)
    assert len(block.encode("utf-8")) <= 600            # notice now counted
    assert "truncated" in block


def test_unwire_removes_only_our_entry(kbhome):
    from cortex.inject import ClaudeCodeAdapter
    _settings(kbhome).parent.mkdir(parents=True, exist_ok=True)
    _settings(kbhome).write_text(json.dumps({
        "hooks": {"SessionStart": [
            {"matcher": "startup",
             "hooks": [{"type": "command", "command": "echo other"}]}]}}))
    a = ClaudeCodeAdapter()
    a.wire(home=kbhome)
    assert a.unwire(home=kbhome) is True
    assert a.is_wired(home=kbhome) is False
    cmds = [h["command"] for e in json.loads(_settings(kbhome).read_text())
            ["hooks"]["SessionStart"] for h in e["hooks"]]
    assert cmds == ["echo other"]                         # ours gone, other kept
