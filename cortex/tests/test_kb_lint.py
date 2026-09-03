import datetime

import pytest

from cortex import cli, lint


TODAY = datetime.date.today().isoformat()


def _kb(home, ws, slug, body, *, typ="", desc="", updated=TODAY, title=""):
    d = home / ".cortex/workspaces" / ws / "knowledge"
    d.mkdir(parents=True, exist_ok=True)
    fm = ["---"]
    if title:
        fm.append(f"title: {title}")
    if typ:
        fm.append(f"type: {typ}")
    fm += ["author: agent", "created: 2026-01-01"]
    if updated is not None:
        fm.append(f"updated: {updated}")
    if desc:
        fm.append(f"description: {desc}")
    fm.append("---")
    (d / f"{slug}.md").write_text("\n".join(fm) + f"\n\n{body}\n")
    return d / f"{slug}.md"


def _task(home, ws, sess, slug, body, *, extra_fm=(), archived=False):
    branch = "archive" if archived else "sessions"
    d = home / ".cortex/workspaces" / ws / branch / sess / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    fm = ["---", "status: Open", *extra_fm, "---"]
    (d / f"{slug}.md").write_text("\n".join(fm) + f"\n\n# {slug}\n\n{body}\n")
    return d / f"{slug}.md"


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "h"
    ws = h / ".cortex/workspaces/ws-a"
    (ws / "sessions/s1/tasks").mkdir(parents=True)
    (ws / "sessions/s1/workbench").mkdir(parents=True)
    (ws / "knowledge").mkdir(parents=True)
    (ws / ".active.t").write_text("s1\n")
    (ws / "sessions/s1/SUMMARY.md").write_text("---\nslug: s1\n---\n\n# s1\n")
    monkeypatch.setenv("HOME", str(h))
    return h


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "proj"
    (r / "pkg").mkdir(parents=True)
    (r / "pkg/live.py").write_text(
        "def live_symbol():\n    pass\n\nclass LiveClass:\n    pass\n"
        "# accepts --real-flag and --kept\n")
    (r / "README.md").write_text("docs\n")
    return r


def _run(*argv):
    return cli.main(["kb", "lint", *argv])


# ---- broken-ref ----

def test_broken_ref_unrepairable_and_repairable(home, capsys):
    _task(home, "ws-a", "s1", "task-a",
          "Blocked by: [task-gone]\nRelated to: [wrong/task-b]")
    _task(home, "ws-a", "s1", "task-b", "b")
    assert _run("--workspace", "ws-a", "--check", "broken-ref") == 0
    out = capsys.readouterr().out
    assert "task-gone (no such doc)" in out
    assert "wrong/task-b -> task-b (repairable)" in out


def test_broken_ref_ambiguous_slug_is_not_repairable(home, capsys):
    _kb(home, "ws-a", "dup", "x", desc="d")
    (home / ".cortex/workspaces/ws-b/knowledge").mkdir(parents=True)
    _kb(home, "ws-b", "dup", "y", desc="d")
    _task(home, "ws-a", "s1", "task-a", "Related to: [nowhere/dup]")
    _run("--workspace", "ws-a", "--check", "broken-ref")
    out = capsys.readouterr().out
    assert "nowhere/dup (no such doc)" in out
    assert "repairable" not in out


def test_link_to_archived_task_is_not_broken(home, capsys):
    _task(home, "ws-a", "old", "task-hist", "done", archived=True)
    _task(home, "ws-a", "s1", "task-a", "Related to: [old/task-hist]")
    assert _run("--workspace", "ws-a", "--check", "broken-ref") == 0
    assert "no findings" in capsys.readouterr().out


def test_archived_docs_are_linted_only_with_archive_flag(home, capsys):
    _task(home, "ws-a", "old", "task-hist", "Related to: [task-gone]", archived=True)
    _run("--workspace", "ws-a", "--check", "broken-ref")
    assert "task-gone" not in capsys.readouterr().out
    _run("--workspace", "ws-a", "--check", "broken-ref", "--archive")
    assert "task-gone (no such doc)" in capsys.readouterr().out


def test_markdown_link_label_is_not_a_reference(home, capsys):
    _kb(home, "ws-a", "note", "See [label](some/path.md) for details.", desc="d")
    assert _run("--workspace", "ws-a", "--check", "broken-ref") == 0
    out = capsys.readouterr().out
    assert "label" not in out
    assert "no findings" in out


# ---- --fix ----

def test_fix_rewrites_only_repairable_and_preserves_the_rest(home, capsys):
    p = _task(home, "ws-a", "s1", "task-a",
              "Blocked by: [task-gone]\nRelated to: [wrong/task-b]",
              extra_fm=("ticket: ABC-1",))
    _task(home, "ws-a", "s1", "task-b", "b")
    before = p.read_text()
    assert _run("--workspace", "ws-a", "--check", "broken-ref", "--fix") == 0
    out = capsys.readouterr().out
    assert "## fixed (addresses rewritten; no claim changed)" in out
    assert "fixed 1 reference in 1 doc" in out
    after = p.read_text()
    assert "Related to: [task-b]" in after
    assert "Blocked by: [task-gone]" in after          # unrepairable, untouched
    assert "ticket: ABC-1" in after                    # frontmatter intact
    assert after.replace("[task-b]", "[wrong/task-b]") == before


def test_fix_does_not_bump_updated(home):
    _kb(home, "ws-a", "target", "t", desc="d", updated="2026-01-02")
    p = _kb(home, "ws-a", "src", "Related to: [nowhere/target]",
            desc="d", updated="2026-01-02")
    _run("--workspace", "ws-a", "--check", "broken-ref", "--fix")
    text = p.read_text()
    assert "updated: 2026-01-02" in text
    assert "knowledge/target" in text


def test_fix_respects_token_boundaries_and_skips_fenced_examples(home, capsys):
    _task(home, "ws-a", "s1", "task-b", "b")
    p = _task(home, "ws-a", "s1", "task-a",
              "Related to: [wrong/task-b]\n"
              "Mentions task-bfoo and wrong/task-bar in prose.\n"
              "```\nRelated to: [wrong/task-b]\n```")
    _run("--workspace", "ws-a", "--check", "broken-ref", "--fix")
    after = p.read_text()
    assert "Related to: [task-b]" in after
    assert "task-bfoo" in after                        # not clobbered
    assert after.count("[wrong/task-b]") == 1          # the fenced one survives


def test_fix_reports_only_the_references_it_actually_rewrote(home, capsys):
    """A file whose fence state differs from the parser's (a ``` inside a
    frontmatter block scalar) can leave one of two repairable references
    untouched. It has to stay a finding: reporting it as fixed on the strength
    of its sibling's replacement would make --strict exit 0 on a broken ref."""
    _task(home, "ws-a", "s1", "task-b", "b")
    _task(home, "ws-a", "s2", "task-c", "c")
    p = _task(home, "ws-a", "s1", "task-a", "Related to: [nowhere/task-c]",
              extra_fm=("related_to: [wrong/task-b]", "notes: |", "  ```"))
    assert _run("--workspace", "ws-a", "--check", "broken-ref",
                "--fix", "--strict") == 1
    out = capsys.readouterr().out
    assert "fixed 1 reference in 1 doc" in out
    after = p.read_text()
    assert "related_to: [task-b]" in after
    assert "Related to: [nowhere/task-c]" in after      # not rewritten...
    assert "nowhere/task-c" in out.split("## fixed")[0]  # ...so still a finding


def test_fix_is_a_no_op_when_nothing_is_repairable(home, capsys):
    p = _task(home, "ws-a", "s1", "task-a", "Related to: [task-gone]")
    before = p.read_text()
    _run("--workspace", "ws-a", "--check", "broken-ref", "--fix")
    out = capsys.readouterr().out
    assert "## fixed" not in out
    assert p.read_text() == before


# ---- dead-ref ----

def test_dead_ref_reports_dead_paths_symbols_and_flags(home, repo, capsys):
    _kb(home, "ws-a", "note",
        "Live: `pkg/live.py`, `live_symbol()`, `LiveClass`, `--real-flag`.\n"
        "Dead: `work_viz/server.py`, `_SSEHub`, `--watch`.",
        desc="d")
    assert _run("--workspace", "ws-a", "--check", "dead-ref",
                "--repo", str(repo)) == 0
    out = capsys.readouterr().out
    assert "work_viz/server.py (path not in proj)" in out
    assert "_SSEHub (symbol not in proj)" in out
    assert "--watch (flag not in proj)" in out
    for live in ("pkg/live.py", "live_symbol", "LiveClass", "--real-flag"):
        assert f"{live} (" not in out


def test_dead_ref_checks_the_head_of_a_valued_flag(home, repo, capsys):
    _kb(home, "ws-a", "note", "Try `--kept=all` and `--vanished=all`.", desc="d")
    _run("--workspace", "ws-a", "--check", "dead-ref", "--repo", str(repo))
    out = capsys.readouterr().out
    assert "--vanished (flag not in proj)" in out
    assert "--kept (" not in out


@pytest.mark.parametrize("body", [
    "Attribute access `args.max` is not a filename.",
    "Home-relative `~/.claude/settings.json` resolves elsewhere.",
    "A placeholder `knowledge/<slug>.md` names nothing.",
    "Prose `and/or` is not a directory.",
    "A bare word `token` is not code-shaped.",
    "```\n`_only_in_a_fence` and `gone/away.py`\n```",
    "An external `https://example.com/x.py` is not ours.",
])
def test_dead_ref_ignores_non_references(home, repo, capsys, body):
    _kb(home, "ws-a", "note", body, desc="d")
    _run("--workspace", "ws-a", "--check", "dead-ref", "--repo", str(repo))
    assert "no findings" in capsys.readouterr().out


def test_dead_ref_finds_a_path_under_a_directory_the_repo_still_has(home, repo, capsys):
    _kb(home, "ws-a", "note", "Look in `pkg/gone` and `nosuch/thing`.", desc="d")
    _run("--workspace", "ws-a", "--check", "dead-ref", "--repo", str(repo))
    out = capsys.readouterr().out
    assert "pkg/gone (path not in proj)" in out
    assert "nosuch/thing" not in out


def test_dead_ref_notes_when_no_repo_is_known(home, capsys):
    _kb(home, "ws-a", "note", "Uses `work_viz/server.py`.", desc="d")
    assert _run("--workspace", "ws-a", "--check", "dead-ref") == 0
    out = capsys.readouterr().out
    assert "## notes" in out
    assert "dead-ref skipped for ws-a: no repo" in out


def test_dead_ref_uses_the_repo_recorded_in_meta(home, repo, capsys):
    (home / ".cortex/workspaces/ws-a/.meta").write_text(f"cwd: {repo}\n")
    _kb(home, "ws-a", "note", "Uses `work_viz/server.py`.", desc="d")
    _run("--workspace", "ws-a", "--check", "dead-ref")
    out = capsys.readouterr().out
    assert "work_viz/server.py (path not in proj)" in out
    assert "## notes" not in out


def test_missing_repo_path_is_an_error(home):
    assert _run("--workspace", "ws-a", "--repo", "/nope/nowhere") == 1


def test_repo_with_workspace_all_is_a_usage_error(home):
    assert _run("--workspace", "all", "--repo", "/tmp") == 2


# ---- orphan / stale / missing-description ----

def test_orphan_counts_authored_backlinks_only(home, capsys):
    _kb(home, "ws-a", "linked", "x", desc="d")
    _kb(home, "ws-a", "lonely", "y", desc="d")
    _task(home, "ws-a", "s1", "task-a", "Related to: [knowledge/linked]")
    _run("--workspace", "ws-a", "--check", "orphan")
    out = capsys.readouterr().out
    assert "ws-a/knowledge/lonely  ->  no authored backlinks" in out
    assert "linked" not in out


def test_stale_thresholds_and_unusable_dates(home, capsys):
    _kb(home, "ws-a", "fresh", "x", desc="d", updated=TODAY)
    _kb(home, "ws-a", "ancient", "x", desc="d", updated="2001-01-01")
    _kb(home, "ws-a", "undated", "x", desc="d", updated=None)
    _kb(home, "ws-a", "garbled", "x", desc="d", updated="last tuesday")
    _run("--workspace", "ws-a", "--check", "stale")
    out = capsys.readouterr().out
    assert "ws-a/knowledge/ancient  ->  updated 2001-01-01" in out
    assert "ws-a/knowledge/undated  ->  no updated: field" in out
    assert "ws-a/knowledge/garbled  ->  unparseable updated: last tuesday" in out
    assert "fresh" not in out


def test_stale_days_is_configurable(home, capsys):
    _kb(home, "ws-a", "recent", "x", desc="d",
        updated=(datetime.date.today() - datetime.timedelta(days=10)).isoformat())
    _run("--workspace", "ws-a", "--check", "stale", "--stale-days", "5")
    assert "recent" in capsys.readouterr().out
    _run("--workspace", "ws-a", "--check", "stale", "--stale-days", "30")
    assert "no findings" in capsys.readouterr().out


def test_missing_description(home, capsys):
    _kb(home, "ws-a", "described", "x", desc="has one")
    _kb(home, "ws-a", "blank", "x")
    _run("--workspace", "ws-a", "--check", "missing-description")
    out = capsys.readouterr().out
    assert "ws-a/knowledge/blank  ->  no description: field" in out
    assert "described" not in out


# ---- the worklist ----

def test_worklist_lists_overlapping_pairs_as_candidates(home, capsys):
    _kb(home, "ws-a", "retry-a", "x", typ="Gotcha",
        desc="retries use exponential backoff jitter")
    _kb(home, "ws-a", "retry-b", "x", typ="Gotcha",
        desc="retries use exponential backoff jitter")
    _kb(home, "ws-a", "other", "x", typ="Decision", desc="unrelated subject matter")
    _run("--workspace", "ws-a", "--check", "overlap")
    out = capsys.readouterr().out
    assert "## agent worklist (needs judgment)" in out
    assert "ws-a/knowledge/retry-a  ~  ws-a/knowledge/retry-b" in out
    assert "other" not in out.split("## agent worklist")[1]
    assert "no findings" in out                    # candidates are not findings


def test_worklist_is_opt_out_via_check(home, capsys):
    _kb(home, "ws-a", "retry-a", "x", typ="Gotcha", desc="retries backoff jitter here")
    _kb(home, "ws-a", "retry-b", "x", typ="Gotcha", desc="retries backoff jitter here")
    _run("--workspace", "ws-a", "--check", "orphan")
    assert "## agent worklist" not in capsys.readouterr().out
    _run("--workspace", "ws-a")
    assert "## agent worklist" in capsys.readouterr().out


def test_worklist_ignores_pairs_of_different_types(home, capsys):
    _kb(home, "ws-a", "a1", "x", typ="Gotcha", desc="retries backoff jitter here")
    _kb(home, "ws-a", "b1", "x", typ="Decision", desc="retries backoff jitter here")
    _run("--workspace", "ws-a", "--check", "overlap")
    assert "## agent worklist" not in capsys.readouterr().out


# ---- output shape and flags ----

def test_check_filter_selects_a_single_check(home, capsys):
    _kb(home, "ws-a", "blank", "Related to: [task-gone]")
    _run("--workspace", "ws-a", "--check", "missing-description")
    out = capsys.readouterr().out
    assert "## missing-description" in out
    assert "## broken-ref" not in out


def test_unknown_check_is_a_usage_error(home, capsys):
    assert _run("--workspace", "ws-a", "--check", "nope") == 2
    assert "unknown nope" in capsys.readouterr().err


def test_max_truncates_with_a_notice(home, capsys):
    for i in range(4):
        _kb(home, "ws-a", f"n{i}", "x")
    _run("--workspace", "ws-a", "--check", "missing-description", "--max", "2")
    assert "... 2 more (raise --max)" in capsys.readouterr().out


def test_strict_exits_nonzero_only_when_findings_remain(home):
    _kb(home, "ws-a", "blank", "x")
    assert _run("--workspace", "ws-a", "--check", "missing-description", "--strict") == 1
    assert _run("--workspace", "ws-a", "--check", "orphan", "--strict") == 1
    _kb(home, "ws-a", "fine", "x", desc="d")
    assert _run("--workspace", "ws-a", "--check", "stale", "--strict") == 0


def test_clean_workspace_reports_no_findings(home, capsys):
    _kb(home, "ws-a", "solo", "x", desc="d")
    _task(home, "ws-a", "s1", "task-a", "Related to: [knowledge/solo]")
    assert _run("--workspace", "ws-a", "--check", "stale,missing-description") == 0
    out = capsys.readouterr().out
    assert out.strip().endswith("no findings")


def test_workspace_all_lints_every_workspace(home, capsys):
    _kb(home, "ws-a", "a-blank", "x")
    (home / ".cortex/workspaces/ws-b/knowledge").mkdir(parents=True)
    _kb(home, "ws-b", "b-blank", "x")
    _run("--workspace", "all", "--check", "missing-description")
    out = capsys.readouterr().out
    assert "ws-a/knowledge/a-blank" in out
    assert "ws-b/knowledge/b-blank" in out


def test_details_are_sanitized_before_printing(home, capsys):
    _kb(home, "ws-a", "sneaky", "Related to: [task-​hidden]", desc="d")
    _run("--workspace", "ws-a", "--check", "broken-ref")
    out = capsys.readouterr().out
    assert "​" not in out
    assert "task-hidden (no such doc)" in out


# ---- units ----

@pytest.mark.parametrize("word,expected", [
    ("pkg/live.py", ("path", "pkg/live.py")),
    ("cortex/ingest.py:357", ("path", "cortex/ingest.py")),
    ("docs/cli.md#anchor", ("path", "docs/cli.md")),
    ("cortex/viz/", ("dir-path", "cortex/viz")),
    ("--watch", ("flag", "--watch")),
    ("--workspace=all", ("flag", "--workspace")),
    ("_SSEHub", ("symbol", "_SSEHub")),
    ("parse_world()", ("symbol", "parse_world")),
    ("RepoIndex", ("symbol", "RepoIndex")),     # CamelCase counts as code-shaped
    ("Reference", None),                        # a capitalized noun does not
    ("token", None),                            # nor a bare lowercase word
    ("args.max", None),                         # attribute access
    ("/etc/passwd", None),                      # absolute
    ("../up.py", None),                         # traversing
    ("no", None),                               # too short
])
def test_classify(word, expected):
    assert lint._classify(word) == expected


def test_replace_outside_fences_only_touches_reference_positions():
    text = "\n".join([
        "related_to: [task-foo, task-bar]",   # frontmatter relation: bare counts
        "Related to: task-foo",               # body relation: bare counts
        "See [task-foo] for context.",        # bracketed anywhere: counts
        "The task-foo migration is done.",    # prose: a word, not a reference
        "task-foobar",                        # not the same slug
        "```",
        "Related to: task-foo",               # fenced: an example
        "```",
    ])
    new, n = lint._replace_outside_fences(text, [("task-foo", "s2/task-foo")])
    assert n == 3
    assert new.split("\n") == [
        "related_to: [s2/task-foo, task-bar]",
        "Related to: s2/task-foo",
        "See [s2/task-foo] for context.",
        "The task-foo migration is done.",
        "task-foobar",
        "```",
        "Related to: task-foo",
        "```",
    ]


def test_fix_does_not_rewrite_a_slug_used_as_prose(home, capsys):
    """A slug is also a noun phrase. `--fix` corrects addresses, not sentences."""
    _kb(home, "ws-a", "retry-policy", "target", desc="d")
    p = _kb(home, "ws-a", "note",
            "See [retry-policy].\nThe retry-policy changed last week.", desc="d")
    _run("--workspace", "ws-a", "--check", "broken-ref", "--fix")
    after = p.read_text()
    assert "See [knowledge/retry-policy]." in after
    assert "The retry-policy changed last week." in after
