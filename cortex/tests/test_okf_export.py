"""`cortex okf export`: a workspace's knowledge/ as a self-contained OKF bundle."""
import subprocess

import pytest

from cortex import cli


def _doc(home, slug, *, typ="Reference", title="", desc="", body="body\n", ws="ws-a"):
    kd = home / ".cortex/workspaces" / ws / "knowledge"
    kd.mkdir(parents=True, exist_ok=True)
    head = f"title: {title}\n" if title else ""
    ty = f"type: {typ}\n" if typ else ""
    (kd / f"{slug}.md").write_text(
        f"---\n{head}{ty}author: agent\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        f"description: {desc}\n---\n\n{body}", encoding="utf-8")
    return kd / f"{slug}.md"


@pytest.fixture
def store_docs(kbhome):
    _doc(kbhome, "auth-tokens", typ="Gotcha", title="Auth tokens",
         desc="Tokens expire after 15m",
         body="See [[knowledge/token-refresh]] and [[other-ws/knowledge/gone]].\n")
    _doc(kbhome, "token-refresh", typ="Reference", title="Token refresh",
         desc="How refresh works")
    return kbhome


def _run(out, *extra):
    return cli.main(["okf", "export", "--workspace", "ws-a", "--out", str(out), *extra])


def test_every_concept_lands_in_the_bundle_with_its_index_and_log(
        store_docs, tmp_path, capsys):
    out = tmp_path / "bundle"
    assert _run(out) == 0
    assert sorted(p.name for p in out.glob("*.md")) == \
        ["auth-tokens.md", "index.md", "log.md", "token-refresh.md"]
    assert str(out) in capsys.readouterr().out


def test_a_resolved_reference_travels_as_a_bundle_absolute_link(store_docs, tmp_path,
                                                                capsys):
    out = tmp_path / "bundle"
    _run(out)
    body = (out / "auth-tokens.md").read_text()
    assert "[Token refresh](/token-refresh.md)" in body
    # An unresolved one is prose, not a link the recipient cannot follow.
    assert "and gone." in body


def test_the_index_is_section_8_and_declares_the_format_version(store_docs, tmp_path,
                                                               capsys):
    out = tmp_path / "bundle"
    _run(out)
    text = (out / "index.md").read_text()
    assert text.startswith("---\nokf_version: 0.2\n---\n")
    assert "## Gotcha" in text
    assert "* [Auth tokens](auth-tokens.md) - Tokens expire after 15m" in text


def test_the_log_carries_the_history_when_the_store_is_a_git_repo(store_docs, tmp_path,
                                                                  capsys):
    st = store_docs / ".cortex"
    for args in (["init", "-q"], ["config", "user.email", "t@example.com"],
                 ["config", "user.name", "t"], ["add", "-A", "."]):
        subprocess.run(["git", *args], cwd=str(st), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "commit", "-q", "-m", "track(kb): new knowledge auth-tokens"],
                   cwd=str(st), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = tmp_path / "bundle"
    _run(out)
    text = (out / "log.md").read_text()
    assert "# Knowledge change log" in text
    assert "**Creation**: [Auth tokens](auth-tokens.md)" in text


def test_a_store_with_no_history_still_exports_and_says_the_log_is_empty(
        store_docs, tmp_path, capsys):
    out = tmp_path / "bundle"
    assert _run(out) == 0
    assert "no git history" in capsys.readouterr().out
    assert "_No knowledge writes" in (out / "log.md").read_text()


def test_a_typeless_doc_fails_the_export_loudly(kbhome, tmp_path, capsys):
    _doc(kbhome, "untyped", typ="")
    out = tmp_path / "bundle"
    assert _run(out) == 1
    err = capsys.readouterr().err
    assert "not conformant" in err and "untyped" in err


def test_a_doc_with_no_frontmatter_fails_the_export_and_keeps_its_body(kbhome,
                                                                      tmp_path, capsys):
    kd = kbhome / ".cortex/workspaces/ws-a/knowledge"
    kd.mkdir(parents=True)
    (kd / "loose.md").write_text("just prose, never given frontmatter\n")
    out = tmp_path / "bundle"
    assert _run(out) == 1
    assert "just prose" in (out / "loose.md").read_text()
    assert "no frontmatter" in capsys.readouterr().err


def test_it_refuses_to_write_into_a_directory_that_holds_files(store_docs, tmp_path,
                                                              capsys):
    out = tmp_path / "bundle"
    out.mkdir()
    (out / "stale.md").write_text("x")
    assert _run(out) == 1
    assert "not empty" in capsys.readouterr().err


def test_a_derived_file_in_the_store_is_not_exported_as_a_concept(store_docs, tmp_path,
                                                                  capsys):
    kd = store_docs / ".cortex/workspaces/ws-a/knowledge"
    (kd / "index.md").write_text("# Knowledge index\n")
    (kd / "log.md").write_text("# Knowledge change log\n")
    out = tmp_path / "bundle"
    _run(out)
    # Both names exist in the bundle, but as the files export derives, so the
    # store's stale copies cannot be what landed.
    assert "okf_version" in (out / "index.md").read_text()


def test_a_round_trip_through_a_bundle_keeps_the_edges(store_docs, tmp_path, capsys):
    out = tmp_path / "bundle"
    _run(out)
    (store_docs / ".cortex/workspaces/ws-b/knowledge").mkdir(parents=True)
    assert cli.main(["okf", "import", str(out), "--workspace", "ws-b", "--write"]) == 0
    body = (store_docs / ".cortex/workspaces/ws-b/knowledge/auth-tokens.md").read_text()
    assert "[[knowledge/token-refresh]]" in body
