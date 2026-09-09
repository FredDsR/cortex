import unicodedata

from cortex.sanitize import sanitize


def test_strips_the_reported_codepoints():
    # The exact input from issue #35, which survived _oneline() untouched:
    # ZWSP, RLO, BOM.
    assert sanitize("​‮﻿") == ""


def test_strips_zero_width_and_bidi_marks():
    for cp in range(0x200B, 0x2010):
        assert sanitize(chr(cp)) == "", hex(cp)


def test_strips_bidi_overrides_and_isolates():
    for cp in list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A)):
        assert sanitize(chr(cp)) == "", hex(cp)


def test_strips_format_private_use_and_unassigned():
    soft_hyphen, private_use, unassigned = "­", "", "͸"
    assert unicodedata.category(soft_hyphen) == "Cf"
    assert unicodedata.category(private_use) == "Co"
    assert unicodedata.category(unassigned) == "Cn"
    assert sanitize(f"a{soft_hyphen}b{private_use}c{unassigned}d") == "abcd"


def test_strips_ansi_escapes_and_nulls_but_keeps_newlines():
    assert sanitize("a\x1b[2Jb\x00c") == "a[2Jbc"
    assert sanitize("one\ntwo\r\nthree\tfour") == "one\ntwo\r\nthree\tfour"


def test_strips_lone_surrogates_so_the_write_cannot_crash():
    # json.loads() accepts "\ud800" happily; encoding it to utf-8 raises.
    assert sanitize("a\ud800b") == "ab"
    sanitize("a\ud800b").encode("utf-8")


def test_nfkc_normalizes():
    assert sanitize("ﬁle") == "file"            # fi ligature
    assert sanitize("ａｂ") == "ab"          # fullwidth latin


def test_reaches_a_fixpoint_on_nested_construction():
    nested = "​" * 3 + "ﬁ" + "‮" * 3
    out = sanitize(nested)
    assert out == "fi"
    assert sanitize(out) == out


def test_leaves_ordinary_text_unchanged():
    for s in ("List users", "Create order: v2 # urgent", "GET /users/{id}",
              "DECIMAL(10,2)", "café naïve", "日本語"):
        assert sanitize(s) == s


def test_accepts_non_str():
    assert sanitize(42) == "42"
    assert sanitize(None) == "None"
