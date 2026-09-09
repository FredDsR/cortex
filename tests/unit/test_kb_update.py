import datetime
from cortex import cli

TODAY = datetime.date.today().isoformat()


def _seed(kbhome):
    path = kbhome / ".cortex/workspaces/ws-a/knowledge/note.md"
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


def _seed_with_extras(kbhome):
    path = kbhome / ".cortex/workspaces/ws-a/knowledge/probe.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntitle: Probe\ntype: Gotcha\nauthor: human\n"
        "created: 2026-08-01\nupdated: 2026-08-01\ndescription: a summary\n"
        "ticket: PROJ-123\npr: 42\ncustom_field: keep-me\n"
        "---\n\nprobe body\n")
    return path


def test_update_preserves_unknown_frontmatter_keys(kbhome):
    path = _seed_with_extras(kbhome)
    assert cli.main(["kb", "update", "knowledge", "probe", "--title", "Probe v2"]) == 0
    t = path.read_text()
    assert "ticket: PROJ-123" in t
    assert "pr: 42" in t
    assert "custom_field: keep-me" in t
    assert "title: Probe v2" in t and f"updated: {TODAY}" in t


def test_update_writes_unknown_keys_after_the_canonical_block(kbhome):
    path = _seed_with_extras(kbhome)
    cli.main(["kb", "update", "knowledge", "probe"])
    assert path.read_text() == (
        "---\ntitle: Probe\ntype: Gotcha\nauthor: human\n"
        f"created: 2026-08-01\nupdated: {TODAY}\ndescription: a summary\n"
        "ticket: PROJ-123\npr: 42\ncustom_field: keep-me\n"
        "---\n\nprobe body")


def test_update_does_not_requote_a_flow_list_value(kbhome):
    path = kbhome / ".cortex/workspaces/ws-a/knowledge/linked.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntitle: Linked\nauthor: agent\ncreated: 2026-08-01\n"
        "updated: 2026-08-01\nblocked_by: [task-foo, task-bar]\n---\n\nb\n")
    cli.main(["kb", "update", "knowledge", "linked"])
    assert "blocked_by: [task-foo, task-bar]" in path.read_text()


def test_update_without_extras_is_unchanged_apart_from_updated(kbhome):
    path = _seed(kbhome)
    cli.main(["kb", "update", "knowledge", "note"])
    assert path.read_text() == (
        "---\ntitle: Original\ntype: Reference\nauthor: agent\n"
        f"created: 2026-01-01\nupdated: {TODAY}\ndescription: original desc\n"
        "---\n\noriginal body")
