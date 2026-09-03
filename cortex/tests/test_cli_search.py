import shutil

from cortex import cli as cortex_cli
from cortex.conftest import FIXTURES


def _home_with_fixtures(tmp_path, monkeypatch):
    root = tmp_path / ".cortex" / "workspaces"
    root.mkdir(parents=True)
    for sub in ("demo-ws", "other-ws", "kb-ghosts-ws", "authored-ws"):
        shutil.copytree(FIXTURES / sub, root / sub)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _ws(tmp_path, monkeypatch, name="wsa"):
    """A single hand-built workspace with one active pointer, so the workspace
    resolves with no --workspace flag."""
    ws = tmp_path / ".cortex" / "workspaces" / name
    (ws / "knowledge").mkdir(parents=True)
    (ws / "sessions" / "s1" / "tasks").mkdir(parents=True)
    (ws / "sessions" / "s1" / "workbench").mkdir()
    (ws / ".active.testid").write_text("s1\n")
    (ws / "sessions" / "s1" / "SUMMARY.md").write_text(
        "---\nslug: s1\nstatus: Active\n---\n\n# s1\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return ws


def test_search_finds_a_knowledge_doc(tmp_path, monkeypatch, capsys):
    ws = _ws(tmp_path, monkeypatch)
    (ws / "knowledge" / "retry-policy.md").write_text(
        "---\ntype: Decision\ndescription: backoff rules\n---\n\n"
        "# Retry policy\n\nExponential backoff on 5xx responses.\n")
    rc = cortex_cli.main(["query", "search", "backoff"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "wsa/knowledge/retry-policy" in out
    assert "knowledge" in out


def test_multiple_terms_are_joined(tmp_path, monkeypatch, capsys):
    ws = _ws(tmp_path, monkeypatch)
    (ws / "knowledge" / "k1.md").write_text(
        "---\n---\n\n# K1\n\nExponential backoff on retries.\n")
    rc = cortex_cli.main(["query", "search", "exponential", "backoff"])
    assert rc == 0
    assert "wsa/knowledge/k1" in capsys.readouterr().out


def test_kind_task_returns_only_tasks(tmp_path, monkeypatch, capsys):
    ws = _ws(tmp_path, monkeypatch)
    (ws / "knowledge" / "k1.md").write_text("---\n---\n\n# K1\n\nretry here\n")
    (ws / "sessions" / "s1" / "tasks" / "t1.md").write_text(
        "---\nstatus: Open\n---\n\n# T1\n\nretry here\n")
    rc = cortex_cli.main(["query", "search", "retry", "--kind", "task"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "wsa/s1/task/t1" in out
    assert "wsa/knowledge/k1" not in out


def test_kind_all_returns_both_kinds(tmp_path, monkeypatch, capsys):
    ws = _ws(tmp_path, monkeypatch)
    (ws / "knowledge" / "k1.md").write_text("---\n---\n\n# K1\n\nretry here\n")
    (ws / "sessions" / "s1" / "tasks" / "t1.md").write_text(
        "---\nstatus: Open\n---\n\n# T1\n\nretry here\n")
    rc = cortex_cli.main(["query", "search", "retry"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "wsa/knowledge/k1" in out and "wsa/s1/task/t1" in out


def test_kind_workbench_returns_only_workbench(tmp_path, monkeypatch, capsys):
    ws = _ws(tmp_path, monkeypatch)
    (ws / "knowledge" / "k1.md").write_text("---\n---\n\n# K1\n\nretry here\n")
    (ws / "sessions" / "s1" / "workbench" / "wb1.md").write_text(
        "---\n---\n\n# WB1\n\nretry here\n")
    rc = cortex_cli.main(["query", "search", "retry", "--kind", "workbench"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "wsa/s1/workbench/wb1" in out
    assert "wsa/knowledge/k1" not in out


def test_workspace_scopes_and_all_crosses(tmp_path, monkeypatch, capsys):
    root = tmp_path / ".cortex" / "workspaces"
    for name in ("wsa", "wsb"):
        (root / name / "knowledge").mkdir(parents=True)
        (root / name / "knowledge" / f"{name}-note.md").write_text(
            "---\n---\n\n# Note\n\nshared retry term\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    rc = cortex_cli.main(["query", "search", "retry", "--workspace", "wsa"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "wsa/knowledge/wsa-note" in out and "wsb/" not in out

    rc = cortex_cli.main(["query", "search", "retry", "--workspace", "all"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "wsa/knowledge/wsa-note" in out and "wsb/knowledge/wsb-note" in out


def test_archive_flag_gates_archived_sessions(tmp_path, monkeypatch, capsys):
    ws = _ws(tmp_path, monkeypatch)
    arch = ws / "archive" / "2026-01-01-old" / "tasks"
    arch.mkdir(parents=True)
    (ws / "archive" / "2026-01-01-old" / "SUMMARY.md").write_text(
        "---\nslug: old\nstatus: Closed\n---\n\n# old\n")
    (arch / "t-old.md").write_text(
        "---\nstatus: Resolved\n---\n\n# Old\n\nretry here\n")

    rc = cortex_cli.main(["query", "search", "retry"])
    assert rc == 0
    assert "t-old" not in capsys.readouterr().out

    rc = cortex_cli.main(["query", "search", "retry", "--archive"])
    assert rc == 0
    assert "t-old" in capsys.readouterr().out


def test_max_truncates_and_reports_the_remainder(tmp_path, monkeypatch, capsys):
    ws = _ws(tmp_path, monkeypatch)
    for i in range(4):
        (ws / "knowledge" / f"k{i}.md").write_text(
            "---\n---\n\n# K\n\nretry here\n")
    rc = cortex_cli.main(["query", "search", "retry", "--max", "2"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.count("wsa/knowledge/") == 2
    assert "(+2 more; raise --max)" in out


def test_full_result_prints_no_remainder_line(tmp_path, monkeypatch, capsys):
    ws = _ws(tmp_path, monkeypatch)
    (ws / "knowledge" / "k1.md").write_text("---\n---\n\n# K1\n\nretry here\n")
    rc = cortex_cli.main(["query", "search", "retry"])
    assert rc == 0
    assert "more; raise --max" not in capsys.readouterr().out


def test_bad_max_exits_1(tmp_path, monkeypatch, capsys):
    _ws(tmp_path, monkeypatch)
    rc = cortex_cli.main(["query", "search", "retry", "--max", "notanint"])
    assert rc == 1
    assert "--max" in capsys.readouterr().err


def test_zero_max_exits_1(tmp_path, monkeypatch):
    _ws(tmp_path, monkeypatch)
    assert cortex_cli.main(["query", "search", "retry", "--max", "0"]) == 1


def test_no_match_exits_0_with_a_message(tmp_path, monkeypatch, capsys):
    ws = _ws(tmp_path, monkeypatch)
    (ws / "knowledge" / "k1.md").write_text("---\n---\n\n# K1\n\nretry here\n")
    rc = cortex_cli.main(["query", "search", "zzzznotpresent"])
    assert rc == 0
    assert "(no matches)" in capsys.readouterr().out


def test_punctuation_only_query_exits_0(tmp_path, monkeypatch, capsys):
    _ws(tmp_path, monkeypatch)
    rc = cortex_cli.main(["query", "search", "..."])
    assert rc == 0
    assert "(no matches)" in capsys.readouterr().out


def test_snippet_is_sanitized_in_output(tmp_path, monkeypatch, capsys):
    ws = _ws(tmp_path, monkeypatch)
    (ws / "knowledge" / "k1.md").write_text(
        "---\n---\n\n# K1\n\nretry ‮ reversed ​ text\n")
    rc = cortex_cli.main(["query", "search", "retry"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "‮" not in out and "​" not in out


def test_unknown_workspace_exits_1(tmp_path, monkeypatch, capsys):
    _ws(tmp_path, monkeypatch)
    rc = cortex_cli.main(["query", "search", "retry", "--workspace", "nope"])
    assert rc == 1
    assert "nope" in capsys.readouterr().err


def test_search_over_the_shared_fixture_tree(tmp_path, monkeypatch, capsys):
    _home_with_fixtures(tmp_path, monkeypatch)
    rc = cortex_cli.main(["query", "search", "task", "--workspace", "all"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "demo-ws/" in out


def test_search_is_listed_in_query_help(capsys):
    rc = cortex_cli.main(["query", "--help"])
    assert rc == 0
    assert "search" in capsys.readouterr().out
