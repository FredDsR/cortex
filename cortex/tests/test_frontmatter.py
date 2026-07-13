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
    assert body == "line one\nline two"    # leading blank + trailing newlines stripped (bash parity)
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


def test_scalar_quotes_trailing_newline_value():
    # Python `$` would wrongly treat this as safe; bash quotes it. Parity: quote.
    assert fm.scalar("why we chose X\n").startswith('"')


def test_split_strips_trailing_newlines_from_body():
    # bash captures FM_BODY via $(...), which strips all trailing newlines.
    text = "---\nauthor: agent\ncreated: 2026-07-09\n---\n\nbody text\n\n"
    _, body = fm.split(text)
    assert body == "body text"


def test_split_lines_returns_raw_slices():
    from cortex import frontmatter as fm
    text = "---\ntitle: T\nauthor: agent\n---\n\nbody line\n"
    fm_lines, body_lines, close = fm.split_lines(text)
    assert fm_lines == ["title: T", "author: agent"]
    # body_lines are raw (separator blank + trailing "" from the final newline preserved)
    assert body_lines == ["", "body line", ""]
    assert close == 3


def test_split_lines_none_without_frontmatter():
    from cortex import frontmatter as fm
    assert fm.split_lines("no frontmatter here\n") == (None, None, None)


def test_split_delegates_to_split_lines_unchanged():
    from cortex import frontmatter as fm
    text = "---\ntitle: T\nauthor: agent\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\nbody\n"
    block, body = fm.split(text)
    assert block == "title: T\nauthor: agent\ncreated: 2026-01-01\nupdated: 2026-01-01"
    assert body == "body"


def test_split_lines_exact_by_default_tolerant_on_opt_in():
    from cortex import frontmatter as fm
    padded = "--- \ntitle: T\nauthor: agent\n --- \n\nbody\n"
    # default (engine): a padded fence is NOT frontmatter
    assert fm.split_lines(padded) == (None, None, None)
    # tolerant (migrator opt-in): padded fence recognized
    fm_lines, body_lines, close = fm.split_lines(padded, tolerant=True)
    assert fm_lines == ["title: T", "author: agent"]
    assert close == 3
