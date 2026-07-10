import datetime
from cortex import cli

TODAY = datetime.date.today().isoformat()


def _seed(kbhome):
    path = kbhome / ".work/workspaces/ws-a/knowledge/note.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntitle: Original\ntype: Reference\nauthor: agent\n"
        "created: 2026-01-01\nupdated: 2026-01-01\ndescription: original desc\n"
        "---\n\noriginal body\n")
    return path


def test_update_missing_file_errors(kbhome):
    assert cli.main(["kb", "update", "knowledge", "does-not-exist"]) == 1


def test_update_touch_bumps_updated_preserves_rest(kbhome):
    path = _seed(kbhome)
    assert cli.main(["kb", "update", "knowledge", "note"]) == 0
    t = path.read_text()
    assert "created: 2026-01-01" in t
    assert f"updated: {TODAY}" in t
    assert "title: Original" in t and "type: Reference" in t
    assert "description: original desc" in t
    assert "original body" in t


def test_update_field_merge_keeps_others(kbhome):
    path = _seed(kbhome)
    cli.main(["kb", "update", "knowledge", "note", "--description", "new desc"])
    t = path.read_text()
    assert "description: new desc" in t
    assert "title: Original" in t and "type: Reference" in t
    assert "original body" in t


def test_update_body_replace(kbhome):
    path = _seed(kbhome)
    cli.main(["kb", "update", "knowledge", "note", "--body", "replaced body"])
    t = path.read_text()
    assert "replaced body" in t and "original body" not in t
    assert "title: Original" in t
