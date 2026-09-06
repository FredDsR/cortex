"""`cortex kb log`: an OKF v0.2 §9 change log derived from the store's git history."""
import subprocess

import pytest

from cortex import changelog, cli, model


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), check=True,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _repo(home):
    """Turn the temp store into a git repo. Deliberately no `origin`: history
    exists the moment somebody runs `git init`, and requiring a remote would
    refuse to derive a log from a perfectly good local one."""
    store = home / ".cortex"
    _git(["init", "-q"], store)
    _git(["config", "user.email", "t@example.com"], store)
    _git(["config", "user.name", "t"], store)
    return store


def _doc(home, slug, *, typ="Reference", desc="", title="", ws="ws-a"):
    kd = home / ".cortex/workspaces" / ws / "knowledge"
    kd.mkdir(parents=True, exist_ok=True)
    head = f"title: {title}\n" if title else ""
    body = f"---\n{head}type: {typ}\nauthor: agent\ncreated: 2026-01-01\n" \
           f"updated: 2026-01-01\ndescription: {desc}\n---\n\nbody\n"
    (kd / f"{slug}.md").write_text(body)
    return kd / f"{slug}.md"


def _commit(store, subject, *, date="2026-05-01"):
    _git(["add", "-A", "."], store)
    env = {"GIT_AUTHOR_DATE": f"{date}T12:00:00", "GIT_COMMITTER_DATE": f"{date}T12:00:00"}
    subprocess.run(["git", "commit", "-q", "-m", subject], cwd=str(store), check=True,
                   env={**__import__("os").environ, **env},
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---- subject parsing ----

@pytest.mark.parametrize("subject,want", [
    ("track(kb): new knowledge auth-tokens", ("new", "auth-tokens")),
    ("track(kb): update knowledge auth-tokens", ("update", "auth-tokens")),
    # `add` is the bash work-kb spelling of `new`, used until the Python port.
    # A real store has 60 of them; dropping it loses a fifth of all creations.
    ("track(kb): add knowledge auth-tokens", ("add", "auth-tokens")),
])
def test_parses_the_structured_subjects(subject, want):
    assert changelog.parse_subject(subject) == want


@pytest.mark.parametrize("subject", [
    "track(kb): index knowledge index.md",      # the tool's own bookkeeping
    "track(kb): index knowledge INDEX",         # ... and its pre-#50 spelling
    "track(kb): lint refs 3 docs",
    "track(kb): new workbench draft",           # session-scoped, not a bundle
    "track(kb): update workbench draft",
    "track: close day some-session",
    "track(kb): spec in the wikilink picker",   # prose that starts the same way
    "track(kb): new knowledge Bad_Slug",        # not a slug
    "chore: unrelated",
])
def test_ignores_everything_that_is_not_a_knowledge_write(subject):
    assert changelog.parse_subject(subject) is None


# ---- reserved names ----

def test_log_md_is_reserved_like_index_md():
    # §9 says log.md carries no frontmatter. If it parsed as a knowledge doc it
    # would land in the index, in search, and -- having no type -- as an `okf`
    # finding against a file cortex derived itself.
    assert model.is_reserved("log.md")
    assert model.is_reserved("LOG.md")
    assert model.is_reserved("index.md")
    assert not model.is_reserved("logs.md")


def test_a_derived_log_never_becomes_a_knowledge_doc(kbhome, capsys):
    _doc(kbhome, "apple", desc="a decision")
    kd = kbhome / ".cortex/workspaces/ws-a/knowledge"
    (kd / "log.md").write_text("# Knowledge change log\n\n## 2026-05-01\n* **Creation**: x\n")
    assert cli.main(["kb", "index", "--workspace", "ws-a"]) == 0
    assert "log" not in capsys.readouterr().out.replace("a decision", "")
    capsys.readouterr()
    cli.main(["kb", "lint", "--workspace", "ws-a", "--check", "okf"])
    assert "no findings" in capsys.readouterr().out


# ---- rendering ----

def test_renders_section_9_shape(kbhome, capsys):
    store = _repo(kbhome)
    _doc(kbhome, "auth-tokens", desc="why we pin v2", title="Auth tokens")
    _commit(store, "track(kb): new knowledge auth-tokens", date="2026-05-22")
    assert cli.main(["kb", "log", "--workspace", "ws-a"]) == 0
    out = capsys.readouterr().out
    assert "# Knowledge change log" in out
    assert "## 2026-05-22" in out
    assert "* **Creation**: [Auth tokens](auth-tokens.md) - why we pin v2" in out


def test_update_verb_renders_as_update(kbhome, capsys):
    store = _repo(kbhome)
    _doc(kbhome, "auth-tokens", desc="d")
    _commit(store, "track(kb): new knowledge auth-tokens", date="2026-05-20")
    (kbhome / ".cortex/workspaces/ws-a/knowledge/auth-tokens.md").write_text(
        "---\ntype: Reference\nauthor: agent\ncreated: 2026-01-01\n"
        "updated: 2026-01-02\ndescription: d\n---\n\nchanged\n")
    _commit(store, "track(kb): update knowledge auth-tokens", date="2026-05-21")
    out = (cli.main(["kb", "log", "--workspace", "ws-a"]), capsys.readouterr().out)[1]
    assert "* **Update**: [auth-tokens](auth-tokens.md) - d" in out


def test_add_is_a_creation(kbhome, capsys):
    store = _repo(kbhome)
    _doc(kbhome, "legacy", desc="from the bash era")
    _commit(store, "track(kb): add knowledge legacy", date="2026-05-25")
    cli.main(["kb", "log", "--workspace", "ws-a"])
    assert "* **Creation**: [legacy](legacy.md) - from the bash era" in capsys.readouterr().out


def test_dates_are_newest_first(kbhome, capsys):
    store = _repo(kbhome)
    _doc(kbhome, "one", desc="1")
    _commit(store, "track(kb): new knowledge one", date="2026-05-01")
    _doc(kbhome, "two", desc="2")
    _commit(store, "track(kb): new knowledge two", date="2026-06-01")
    cli.main(["kb", "log", "--workspace", "ws-a"])
    out = capsys.readouterr().out
    assert out.index("## 2026-06-01") < out.index("## 2026-05-01")


def test_index_commits_are_filtered_out(kbhome, capsys):
    store = _repo(kbhome)
    _doc(kbhome, "apple", desc="a")
    _commit(store, "track(kb): new knowledge apple", date="2026-05-01")
    cli.main(["kb", "index", "--workspace", "ws-a", "--write"])
    capsys.readouterr()
    _commit(store, "track(kb): index knowledge index.md", date="2026-05-02")
    cli.main(["kb", "log", "--workspace", "ws-a"])
    out = capsys.readouterr().out
    assert "## 2026-05-02" not in out                    # nothing but bookkeeping
    assert "## 2026-05-01" in out


def test_one_entry_per_doc_per_day_creation_wins(kbhome, capsys):
    store = _repo(kbhome)
    path = _doc(kbhome, "apple", desc="a")
    _commit(store, "track(kb): new knowledge apple", date="2026-05-01")
    for n in range(2):                       # a real edit each time, as kb update does
        path.write_text(path.read_text() + f"\nrevision {n}\n")
        _commit(store, "track(kb): update knowledge apple", date="2026-05-01")
    cli.main(["kb", "log", "--workspace", "ws-a"])
    out = capsys.readouterr().out
    assert len([ln for ln in out.splitlines() if ln.startswith("* ")]) == 1
    assert "**Creation**" in out and "**Update**" not in out


def test_a_deleted_doc_is_recorded_without_a_link(kbhome, capsys):
    # An exported bundle must not carry a link to a file it does not contain;
    # #53 makes that the rule for unresolved references.
    store = _repo(kbhome)
    _doc(kbhome, "gone", desc="d")
    _commit(store, "track(kb): new knowledge gone", date="2026-05-01")
    (kbhome / ".cortex/workspaces/ws-a/knowledge/gone.md").unlink()
    _commit(store, "track: remove it", date="2026-05-02")
    cli.main(["kb", "log", "--workspace", "ws-a"])
    out = capsys.readouterr().out
    assert "* **Creation**: gone - (no longer in the store)" in out
    assert "(gone.md)" not in out


# ---- honesty about coverage ----

def test_header_names_the_range_actually_covered(kbhome, capsys):
    store = _repo(kbhome)
    _doc(kbhome, "one", desc="1")
    _commit(store, "track(kb): new knowledge one", date="2026-05-01")
    _doc(kbhome, "two", desc="2")
    _commit(store, "track(kb): new knowledge two", date="2026-06-01")
    cli.main(["kb", "log", "--workspace", "ws-a"])
    out = capsys.readouterr().out
    assert "2026-05-01 to 2026-06-01" in out


def test_uncommitted_docs_are_declared_not_silently_missing(kbhome, capsys):
    store = _repo(kbhome)
    _doc(kbhome, "committed", desc="c")
    _commit(store, "track(kb): new knowledge committed", date="2026-05-01")
    _doc(kbhome, "pending", desc="not yet committed")
    cli.main(["kb", "log", "--workspace", "ws-a"])
    out = capsys.readouterr().out
    assert "uncommitted" in out
    assert "pending" not in out.split("## 2026-05-01")[0].replace("uncommitted", "")


def test_no_git_says_so_and_writes_nothing(kbhome, capsys):
    _doc(kbhome, "apple", desc="a")               # store is not a git repo
    assert cli.main(["kb", "log", "--workspace", "ws-a", "--write"]) == 0
    out = capsys.readouterr().out + capsys.readouterr().err
    assert "not a git repo" in out
    assert not (kbhome / ".cortex/workspaces/ws-a/knowledge/log.md").exists()


def test_no_git_is_not_an_error(kbhome, capsys):
    _doc(kbhome, "apple", desc="a")
    assert cli.main(["kb", "log", "--workspace", "ws-a"]) == 0


# ---- --write, --since, --max ----

def test_write_derives_a_banner_marked_log(kbhome, capsys):
    store = _repo(kbhome)
    _doc(kbhome, "apple", desc="a decision")
    _commit(store, "track(kb): new knowledge apple", date="2026-05-01")
    assert cli.main(["kb", "log", "--workspace", "ws-a", "--write"]) == 0
    log = kbhome / ".cortex/workspaces/ws-a/knowledge/log.md"
    assert log.is_file()
    text = log.read_text()
    assert "generated by cortex kb log; do not edit" in text
    assert "# Knowledge change log" in text
    assert "* **Creation**: [apple](apple.md) - a decision" in text
    assert not text.startswith("---")            # §9: no frontmatter


def test_since_bounds_the_history_read(kbhome, capsys):
    store = _repo(kbhome)
    _doc(kbhome, "old", desc="o")
    _commit(store, "track(kb): new knowledge old", date="2026-01-01")
    _doc(kbhome, "recent", desc="r")
    _commit(store, "track(kb): new knowledge recent", date="2026-06-01")
    cli.main(["kb", "log", "--workspace", "ws-a", "--since", "2026-05-01"])
    out = capsys.readouterr().out
    assert "recent" in out and "old" not in out


def test_max_caps_stdout_but_not_the_written_file(kbhome, capsys):
    # Same split as `kb index`: `--max` bounds what a terminal prints, while the
    # file is what `cortex okf export` will ship. `--since` is the windowing
    # knob for the file.
    store = _repo(kbhome)
    for i in range(6):
        _doc(kbhome, f"doc-{i}", desc=f"d{i}")
        _commit(store, f"track(kb): new knowledge doc-{i}", date=f"2026-0{i + 1}-01")
    cli.main(["kb", "log", "--workspace", "ws-a", "--max", "2"])
    assert "more (raise --max)" in capsys.readouterr().out
    cli.main(["kb", "log", "--workspace", "ws-a", "--max", "2", "--write"])
    capsys.readouterr()
    text = (kbhome / ".cortex/workspaces/ws-a/knowledge/log.md").read_text()
    assert "more (raise --max)" not in text
    assert text.count("* **Creation**") == 6


def test_bad_max_still_errors(kbhome, capsys):
    _repo(kbhome)
    _doc(kbhome, "apple", desc="a")
    assert cli.main(["kb", "log", "--workspace", "ws-a", "--max", "nope"]) == 1


def test_history_before_a_workspace_rename_is_not_reached(kbhome, capsys):
    """A known limit, pinned so nobody 'fixes' it with something fragile.

    `git log -- .` reads the directory's current path. `--follow` handles a
    renamed *file*, not a renamed directory, so a workspace renamed (see the
    `workspace-slug-drift-on-rename` note) leaves its earlier writes under the
    old path and out of reach. The coverage header stays truthful because it
    reports the range it actually read, which is the whole reason it exists.
    """
    store = _repo(kbhome)
    _doc(kbhome, "early", desc="e", ws="old-name")
    _commit(store, "track(kb): new knowledge early", date="2026-01-01")
    _git(["mv", "workspaces/old-name", "workspaces/new-name"], store)
    _commit(store, "track: rename the workspace", date="2026-02-01")
    _doc(kbhome, "later", desc="l", ws="new-name")
    _commit(store, "track(kb): new knowledge later", date="2026-03-01")

    cli.main(["kb", "log", "--workspace", "new-name"])
    out = capsys.readouterr().out
    assert "later" in out
    assert "early" not in out                     # under the old path
    assert "2026-01-01" not in out                # and the header says so
    assert "2026-02-01 to 2026-03-01" in out
