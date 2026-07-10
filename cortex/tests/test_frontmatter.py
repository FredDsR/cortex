from cortex import frontmatter as fm


def test_scalar_plain_vs_quoted():
    assert fm.scalar("A decision") == "A decision"          # safe: letters/space
    assert fm.scalar("Reference") == "Reference"
    assert fm.scalar("Table accounts (3 columns)") == "Table accounts (3 columns)"
    assert fm.scalar("Create order: v2 # x") == '"Create order: v2 # x"'  # colon/# -> quoted
    assert fm.scalar('has "quote" and \\ back') == '"has \\"quote\\" and \\\\ back"'
    assert fm.scalar("") == '""'


def test_emit_canonical_order_and_bytes():
    doc = fm.emit(
        {"title": "A decision", "type": "Decision", "author": "agent",
         "created": "2026-07-09", "updated": "2026-07-09",
         "description": "why we chose X"},
        "body text")
    assert doc == (
        "---\n"
        "title: A decision\n"
        "type: Decision\n"
        "author: agent\n"
        "created: 2026-07-09\n"
        "updated: 2026-07-09\n"
        "description: why we chose X\n"
        "---\n"
        "\n"
        "body text")


def test_emit_omits_absent_optionals():
    doc = fm.emit({"author": "agent", "created": "2026-07-09",
                   "updated": "2026-07-09"}, "hi")
    assert "title:" not in doc and "type:" not in doc and "description:" not in doc
    assert doc.startswith("---\nauthor: agent\ncreated: 2026-07-09\nupdated: 2026-07-09\n---\n\nhi")


def test_split_extracts_block_and_body():
    text = "---\nauthor: agent\ncreated: 2026-07-09\n---\n\nline one\nline two\n"
    block, body = fm.split(text)
    assert block == "author: agent\ncreated: 2026-07-09"
    assert body == "line one\nline two\n"          # one leading blank stripped
    assert fm.split("no frontmatter\n") == (None, None)


def test_read_field_unwraps_quotes():
    block = 'title: "Create order: v2"\ntype: Decision\nauthor: agent'
    assert fm.read_field(block, "title") == "Create order: v2"   # unquoted
    assert fm.read_field(block, "type") == "Decision"
    assert fm.read_field(block, "missing") == ""


def test_emit_read_roundtrip_through_split():
    doc = fm.emit({"type": "Reference", "author": "agent", "created": "2026-01-01",
                   "updated": "2026-01-01", "description": "Use X: because #y"}, "b")
    block, body = fm.split(doc)
    assert fm.read_field(block, "description") == "Use X: because #y"
    assert body == "b"
