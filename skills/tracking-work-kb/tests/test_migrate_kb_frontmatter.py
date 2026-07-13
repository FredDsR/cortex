import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import migrate_kb_frontmatter as m


def test_backfills_updated_from_created_in_canonical_order():
    text = "---\nauthor: agent\ncreated: 2026-05-23\n---\n\nbody\n"
    new, changed = m.normalize_frontmatter(text)
    assert changed
    fm = new.split("---")[1]
    assert "updated: 2026-05-23" in fm
    # canonical order: author, created, updated
    assert fm.index("author:") < fm.index("created:") < fm.index("updated:")
    assert new.endswith("\nbody\n")  # body untouched


def test_idempotent_when_already_current():
    text = "---\nauthor: agent\ncreated: 2026-05-23\nupdated: 2026-05-23\n---\n\nb\n"
    new, changed = m.normalize_frontmatter(text)
    assert changed is False


def test_body_prose_refs_reported_not_edited():
    text = "---\nauthor: agent\ncreated: 2026-05-23\nupdated: 2026-05-23\n---\n\nrun work-kb index here\n"
    refs = m.stale_refs_in_body(text)
    assert any("work-kb" in line for _, line in refs)
    new, changed = m.normalize_frontmatter(text)
    assert changed is False  # prose is never rewritten by normalize


def test_no_frontmatter_returns_none():
    new, changed = m.normalize_frontmatter("just text, no fm\n")
    assert new is None and changed is False


def test_body_and_trailing_newline_preserved_on_reorder():
    # created before updated is already canonical; force a reorder by omitting
    # updated so it is backfilled, and assert the body (incl. trailing newline)
    # is preserved byte-for-byte.
    text = "---\nauthor: agent\ncreated: 2026-05-23\n---\n\nbody line one\nbody line two\n"
    new, changed = m.normalize_frontmatter(text)
    assert changed
    assert new.endswith("body line one\nbody line two\n")
    assert "updated: 2026-05-23" in new


def test_uses_engine_canon():
    from cortex.frontmatter import CANON as ENGINE_CANON
    assert m.CANON is ENGINE_CANON


def test_padded_fence_still_normalized():
    # A legacy hand-edited doc with a whitespace-padded fence is still migrated
    # (tolerant fence match preserved via split_lines(tolerant=True)).
    text = "--- \nauthor: agent\ncreated: 2026-05-23\n--- \n\nbody\n"
    new, changed = m.normalize_frontmatter(text)
    assert changed
    assert "updated: 2026-05-23" in new
