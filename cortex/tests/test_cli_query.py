import shutil
from pathlib import Path

from cortex import cli as cortex_cli


def _home_with_fixtures(tmp_path, monkeypatch):
    """Build $HOME/.cortex/workspaces/ from the shared fixture tree."""
    from cortex.conftest import FIXTURES
    root = tmp_path / ".cortex" / "workspaces"
    root.mkdir(parents=True)
    for sub in ("demo-ws", "other-ws", "kb-ghosts-ws", "authored-ws"):
        shutil.copytree(FIXTURES / sub, root / sub)
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_neighbors_prints_links(tmp_path, monkeypatch, capsys):
    _home_with_fixtures(tmp_path, monkeypatch)
    rc = cortex_cli.main(["query", "neighbors", "task-a"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "task-b" in out          # outgoing blocked
    assert "beta/task-c" in out     # outgoing related
    assert "Outgoing" in out and "Backlinks" in out


def test_neighbors_lists_ghosts(tmp_path, monkeypatch, capsys):
    _home_with_fixtures(tmp_path, monkeypatch)
    rc = cortex_cli.main(["query", "neighbors", "task-ghosted"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "knowledge/missing-note" in out
    assert "workbench/draft-x" in out


def test_unknown_slug_exits_1(tmp_path, monkeypatch, capsys):
    _home_with_fixtures(tmp_path, monkeypatch)
    rc = cortex_cli.main(["query", "neighbors", "no-such-slug"])
    assert rc == 1
    assert "no-such-slug" in capsys.readouterr().err


def test_ambiguous_slug_lists_candidates(tmp_path, monkeypatch, capsys):
    # Two workspaces with the same task slug -> ambiguous without narrowing.
    root = tmp_path / ".cortex" / "workspaces"
    for ws in ("wsx", "wsy"):
        d = root / ws / "sessions" / "s1" / "tasks"
        d.mkdir(parents=True)
        (root / ws / "sessions" / "s1" / "SUMMARY.md").write_text(
            "---\nslug: s1\nstatus: Active\n---\n\n# s1\n")
        (d / "dup.md").write_text("---\nslug: dup\nstatus: Open\n---\n\n# Dup\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = cortex_cli.main(["query", "neighbors", "dup"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "ambiguous" in err
    assert "wsx/s1/task/dup" in err and "wsy/s1/task/dup" in err
    # narrowing resolves it
    rc2 = cortex_cli.main(["query", "neighbors", "dup", "--workspace", "wsx"])
    assert rc2 == 0


def test_bad_max_exits_1(tmp_path, monkeypatch, capsys):
    _home_with_fixtures(tmp_path, monkeypatch)
    rc = cortex_cli.main(["query", "neighbors", "task-a", "--max", "notanint"])
    assert rc == 1


def test_kind_disambiguates_cross_kind_collision(tmp_path, monkeypatch, capsys):
    # A task and a knowledge doc share slug "dup" in the same workspace.
    ws = tmp_path / ".cortex" / "workspaces" / "wsz"
    (ws / "knowledge").mkdir(parents=True)
    (ws / "sessions" / "s1" / "tasks").mkdir(parents=True)
    (ws / "sessions" / "s1" / "SUMMARY.md").write_text(
        "---\nslug: s1\nstatus: Active\n---\n\n# s1\n")
    (ws / "knowledge" / "dup.md").write_text("---\nslug: dup\n---\n\n# K\n")
    (ws / "sessions" / "s1" / "tasks" / "dup.md").write_text(
        "---\nslug: dup\nstatus: Open\n---\n\n# T\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    # Ambiguous without --kind (workspace alone cannot separate kinds).
    assert cortex_cli.main(["query", "neighbors", "dup", "--workspace", "wsz"]) == 1
    assert "ambiguous" in capsys.readouterr().err
    # --kind resolves it.
    rc = cortex_cli.main(["query", "neighbors", "dup", "--workspace", "wsz", "--kind", "task"])
    assert rc == 0
    assert "wsz/s1/task/dup" in capsys.readouterr().out


def test_query_registered_in_top_level_help(capsys):
    rc = cortex_cli.main(["--help"])
    assert rc == 0
    assert "query" in capsys.readouterr().out


# --- query related ---

def _home_with_knowledge(tmp_path, monkeypatch, docs):
    """$HOME/.cortex/workspaces/relws/knowledge/<slug>.md for each (slug, body)."""
    ws = tmp_path / ".cortex" / "workspaces" / "relws"
    (ws / "knowledge").mkdir(parents=True)
    (ws / "sessions" / "s1" / "tasks").mkdir(parents=True)
    (ws / "sessions" / "s1" / "SUMMARY.md").write_text(
        "---\nslug: s1\nstatus: Active\n---\n\n# s1\n")
    (ws / ".active.testid").write_text("s1\n")
    for slug, body in docs:
        (ws / "knowledge" / f"{slug}.md").write_text(
            f"---\ntitle: {slug}\ndescription: note about {slug}\n---\n\n{body}\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    return ws


def test_related_ranks_candidates_and_names_the_shared_terms(
        tmp_path, monkeypatch, capsys):
    _home_with_knowledge(tmp_path, monkeypatch, [
        ("rebase-policy", "rebase conflict resolution during pull"),
        ("conflict-notes", "rebase conflict resolution walkthrough"),
        ("colour-palette", "teal magenta swatches for the viewer"),
    ])
    rc = cortex_cli.main(["query", "related", "rebase-policy",
                          "--workspace", "relws"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "relws/knowledge/rebase-policy  (candidates: knowledge)" in out
    assert "relws/knowledge/conflict-notes" in out
    assert "shared:" in out
    # The doc itself never appears as its own candidate.
    assert out.count("relws/knowledge/rebase-policy") == 1


def test_related_omits_docs_already_linked_in_either_direction(
        tmp_path, monkeypatch, capsys):
    ws = _home_with_knowledge(tmp_path, monkeypatch, [
        ("rebase-policy", "rebase conflict resolution during pull"),
        ("linked-out", "rebase conflict resolution walkthrough"),
        ("linked-in", "rebase conflict resolution walkthrough"),
        ("unlinked", "rebase conflict resolution walkthrough"),
    ])
    kn = ws / "knowledge"
    kn.joinpath("rebase-policy.md").write_text(
        "---\ntitle: rebase-policy\n---\n\nrebase conflict resolution during"
        " pull. See [[knowledge/linked-out]].\n")
    kn.joinpath("linked-in.md").write_text(
        "---\ntitle: linked-in\n---\n\nrebase conflict resolution walkthrough,"
        " see [[knowledge/rebase-policy]].\n")
    rc = cortex_cli.main(["query", "related", "rebase-policy",
                          "--workspace", "relws"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "knowledge/unlinked" in out
    assert "knowledge/linked-out" not in out
    assert "knowledge/linked-in" not in out


def test_related_reports_no_candidates_rather_than_an_empty_list(
        tmp_path, monkeypatch, capsys):
    _home_with_knowledge(tmp_path, monkeypatch, [("solo", "a lone note")])
    rc = cortex_cli.main(["query", "related", "solo", "--workspace", "relws"])
    assert rc == 0
    assert "(no candidates)" in capsys.readouterr().out


def test_related_min_score_rejects_a_non_number(tmp_path, monkeypatch, capsys):
    _home_with_knowledge(tmp_path, monkeypatch, [("solo", "a lone note")])
    rc = cortex_cli.main(["query", "related", "solo", "--workspace", "relws",
                          "--min-score", "high"])
    assert rc == 1
    assert "--min-score" in capsys.readouterr().err


def test_related_min_score_rejects_a_negative(tmp_path, monkeypatch, capsys):
    _home_with_knowledge(tmp_path, monkeypatch, [("solo", "a lone note")])
    rc = cortex_cli.main(["query", "related", "solo", "--workspace", "relws",
                          "--min-score", "-1"])
    assert rc == 1
    assert "--min-score" in capsys.readouterr().err


def test_related_bounds_the_listing_and_says_what_it_left_out(
        tmp_path, monkeypatch, capsys):
    _home_with_knowledge(tmp_path, monkeypatch, [
        ("target", "rebase conflict resolution")] + [
        (f"cand-{i}", "rebase conflict resolution") for i in range(4)])
    rc = cortex_cli.main(["query", "related", "target", "--workspace", "relws",
                          "--max", "2"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "(+2 more; raise --max)" in out


def test_related_unknown_slug_exits_1(tmp_path, monkeypatch, capsys):
    _home_with_knowledge(tmp_path, monkeypatch, [("solo", "a lone note")])
    rc = cortex_cli.main(["query", "related", "nope", "--workspace", "relws"])
    assert rc == 1
    assert "nope" in capsys.readouterr().err


def test_related_workspace_all_still_resolves_the_slug(
        tmp_path, monkeypatch, capsys):
    # `all` is a scope, not a workspace filter, so it must not be passed through
    # to slug lookup as the literal workspace name "all".
    _home_with_knowledge(tmp_path, monkeypatch, [
        ("rebase-policy", "rebase conflict resolution during pull"),
        ("conflict-notes", "rebase conflict resolution walkthrough"),
    ])
    rc = cortex_cli.main(["query", "related", "rebase-policy",
                          "--workspace", "all"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "relws/knowledge/conflict-notes" in out


def test_related_registered_in_query_help(capsys):
    rc = cortex_cli.main(["query", "--help"])
    assert rc == 0
    assert "related" in capsys.readouterr().out
