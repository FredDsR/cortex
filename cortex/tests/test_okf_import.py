"""`cortex okf import`: reading somebody else's OKF bundle into the store.

The untrusted half of #53. A bundle's `description:` fields land in the
`<cortex-index>` block `cortex inject` hands a fresh agent at SessionStart, so
this is the same exposure #35 fixed on the ingest path, arriving through a new
door.
"""
import pytest

from cortex import cli


def _concept(root, slug, *, body="body\n", **fields):
    f = root / f"{slug}.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    block = "".join(f"{k}: {v}\n" for k, v in fields.items())
    f.write_text(f"---\n{block}---\n\n{body}", encoding="utf-8")
    return f


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "bundle"
    root.mkdir()
    _concept(root, "auth-tokens", type="Gotcha", title="Auth tokens",
             description="Tokens expire after 15m",
             body="See [Refresh](/token-refresh.md) and [spec](https://x.test/a.md).\n")
    _concept(root, "token-refresh", type="Reference", title="Token refresh",
             description="How refresh works")
    (root / "index.md").write_text("# Index\n\n* [Auth tokens](auth-tokens.md) - x\n")
    (root / "log.md").write_text("# Knowledge change log\n\n## 2026-01-01\n")
    return root


def _kdir(home):
    return home / ".cortex/workspaces/ws-a/knowledge"


def _run(bundle, *extra):
    return cli.main(["okf", "import", str(bundle), "--workspace", "ws-a", *extra])


# ---- the contract shared with kb ingest: dry run by default, never overwrite ----

def test_dry_run_lists_the_concepts_and_writes_nothing(kbhome, bundle, capsys):
    assert _run(bundle) == 0
    out = capsys.readouterr().out
    assert "## would create" in out
    assert "auth-tokens [Gotcha] - Tokens expire after 15m" in out
    assert not _kdir(kbhome).exists()


def test_write_creates_the_docs(kbhome, bundle, capsys):
    assert _run(bundle, "--write") == 0
    text = (_kdir(kbhome) / "auth-tokens.md").read_text()
    assert "type: Gotcha" in text and "title: Auth tokens" in text
    assert "## created" in capsys.readouterr().out


def test_an_existing_doc_is_never_overwritten(kbhome, bundle, capsys):
    _kdir(kbhome).mkdir(parents=True)
    (_kdir(kbhome) / "auth-tokens.md").write_text("---\ntype: Decision\n---\n\nmine\n")
    assert _run(bundle, "--write") == 0
    assert "mine" in (_kdir(kbhome) / "auth-tokens.md").read_text()
    out = capsys.readouterr().out
    assert "## skipped (exists)" in out and "auth-tokens" in out


def test_the_bundles_own_derived_files_are_not_concepts(kbhome, bundle, capsys):
    _run(bundle, "--write")
    assert sorted(p.name for p in _kdir(kbhome).glob("*.md")) == \
        ["auth-tokens.md", "token-refresh.md"]


# ---- frontmatter: what maps, and what rides through ----

def test_generated_maps_to_the_dates_and_rides_through_verbatim(kbhome, tmp_path, capsys):
    root = tmp_path / "b"
    root.mkdir()
    (root / "a.md").write_text(
        "---\ntype: Design\ngenerated:\n  by: some-other-wiki\n"
        "  at: 2024-03-04T10:00:00Z\n---\n\nbody\n")
    _run(root, "--write")
    text = (_kdir(kbhome) / "a.md").read_text()
    # `generated.at` is OKF's "last meaningful change", which is `updated`.
    assert "created: 2024-03-04" in text and "updated: 2024-03-04" in text
    # `author` is a two-value field here, so the generator's name cannot go in
    # it; carrying the block verbatim is what keeps that provenance.
    assert "generated:\n  by: some-other-wiki" in text


def test_a_bundles_own_dates_win_over_generated_and_over_today(kbhome, tmp_path,
                                                               capsys):
    # An import is not a re-verification. Stamping `updated` with today would
    # blind `kb lint --check stale` on every doc it touches, which is the same
    # reason #59 keeps a retype away from `kb update`.
    root = tmp_path / "b"
    root.mkdir()
    (root / "a.md").write_text(
        "---\ntype: Design\ncreated: 2025-01-01\nupdated: 2025-06-06\n"
        "generated:\n  at: 2024-03-04T10:00:00Z\n---\n\nbody\n")
    _run(root, "--write")
    text = (_kdir(kbhome) / "a.md").read_text()
    assert "created: 2025-01-01" in text and "updated: 2025-06-06" in text


def test_a_concept_with_no_frontmatter_keeps_its_body(kbhome, tmp_path, capsys):
    # `fm.split` reports (None, None) for a file with no `---` block, so taking
    # its body would import an empty doc over somebody's writing. The export
    # side already carries such a file whole; this is the same choice inbound.
    root = tmp_path / "b"
    root.mkdir()
    (root / "a.md").write_text("just prose, never given frontmatter\n")
    _run(root, "--write")
    assert "just prose" in (_kdir(kbhome) / "a.md").read_text()


def test_generated_keeps_at_when_another_subkey_sits_between(kbhome, tmp_path,
                                                             capsys):
    # A §5 `generated:` block may carry more than `by` and `at`. Reading an
    # unrecognized sub-key as the end of the mapping loses `at`, and losing
    # `at` is exactly the silent stamping this module refuses to do.
    root = tmp_path / "b"
    root.mkdir()
    (root / "a.md").write_text(
        "---\ntype: Design\ngenerated:\n  by: agent\n  model: some-model\n"
        "  at: 2024-03-04T10:00:00Z\n---\n\nbody\n")
    _run(root, "--write")
    assert "updated: 2024-03-04" in (_kdir(kbhome) / "a.md").read_text()


def test_unknown_keys_survive_the_import(kbhome, tmp_path, capsys):
    root = tmp_path / "b"
    root.mkdir()
    (root / "a.md").write_text(
        "---\ntype: Design\ntags: [auth, tokens]\nstatus: stable\n---\n\nbody\n")
    _run(root, "--write")
    text = (_kdir(kbhome) / "a.md").read_text()
    assert "tags: [auth, tokens]" in text and "status: stable" in text


def test_a_typeless_concept_is_imported_and_reported(kbhome, tmp_path, capsys):
    root = tmp_path / "b"
    root.mkdir()
    (root / "a.md").write_text("---\ntitle: A\n---\n\nbody\n")
    assert _run(root, "--write") == 0
    assert (_kdir(kbhome) / "a.md").is_file()
    out = capsys.readouterr().out
    assert "no type" in out and "a.md" in out


# ---- links ----

def test_links_between_concepts_become_wikilinks_and_external_ones_do_not(
        kbhome, bundle, capsys):
    _run(bundle, "--write")
    body = (_kdir(kbhome) / "auth-tokens.md").read_text()
    assert "[[knowledge/token-refresh]]" in body
    assert "[spec](https://x.test/a.md)" in body


# ---- sanitization: every string, not the ones that look risky ----

def test_every_extracted_string_is_sanitized(kbhome, tmp_path, capsys):
    root = tmp_path / "b"
    root.mkdir()
    (root / "a.md").write_text(
        "---\ntype: Design\ntitle: \"A​B\"\n"
        "description: \"drop ‮txet\"\nnote: \"x​y\"\n---\n\n"
        "body ‮reversed\n", encoding="utf-8")
    _run(root, "--write")
    text = (_kdir(kbhome) / "a.md").read_text()
    assert "​" not in text and "‮" not in text
    assert "title: AB" in text                       # frontmatter value
    assert "note: \"xy\"" in text                    # an unknown key's line
    assert "body reversed" in text                   # and the body


# ---- shape of the bundle ----

def test_a_nested_bundle_lands_flat(kbhome, tmp_path, capsys):
    root = tmp_path / "b"
    root.mkdir()
    _concept(root / "concepts", "deep", type="Reference")
    _run(root, "--write")
    assert (_kdir(kbhome) / "deep.md").is_file()


def test_a_duplicate_stem_keeps_the_first_and_says_so(kbhome, tmp_path, capsys):
    root = tmp_path / "b"
    root.mkdir()
    _concept(root, "dup", type="Reference", description="first")
    _concept(root / "sub", "dup", type="Reference", description="second")
    _run(root, "--write")
    assert "first" in (_kdir(kbhome) / "dup.md").read_text()
    assert "duplicate" in capsys.readouterr().out


def test_a_filename_that_is_not_a_slug_is_reported_not_written(kbhome, tmp_path, capsys):
    root = tmp_path / "b"
    root.mkdir()
    _concept(root, "Not A Slug", type="Reference")
    _concept(root, "fine", type="Reference")
    assert _run(root, "--write") == 0
    assert [p.name for p in _kdir(kbhome).glob("*.md")] == ["fine.md"]
    assert "invalid slug" in capsys.readouterr().out


def test_a_missing_bundle_is_an_error(kbhome, tmp_path, capsys):
    assert _run(tmp_path / "nope") == 1
    assert "not found" in capsys.readouterr().err


def test_a_missing_bundle_is_reported_before_an_ambiguous_workspace(kbhome, tmp_path,
                                                                    capsys):
    # A missing path is the caller's typo. Resolving the workspace first would
    # answer it with "pass --workspace", sending them after the wrong thing.
    other = kbhome / ".cortex/workspaces/ws-b"
    (other / "sessions" / "s" / "workbench").mkdir(parents=True)
    (other / ".active.testid").write_text("s\n")
    assert cli.main(["okf", "import", str(tmp_path / "nope")]) == 1
    assert "bundle not found" in capsys.readouterr().err
