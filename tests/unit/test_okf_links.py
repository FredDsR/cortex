"""Link translation at the OKF bundle boundary, both directions."""
import pytest

from cortex.okf import links


def _resolve(ref):
    """The bundle holds one doc: `auth-tokens`, titled `Auth [token] expiry`."""
    slug = ref.rsplit("/", 1)[-1]
    return (slug, "Auth [token] expiry") if slug == "auth-tokens" else None


def _is_doc(stem):
    return stem in ("auth-tokens", "token-refresh")


# ---- export: [[wikilink]] -> markdown ----

@pytest.mark.parametrize("ref", ["auth-tokens", "knowledge/auth-tokens"])
def test_a_resolved_reference_becomes_a_bundle_absolute_link(ref):
    # §7 recommends bundle-absolute over relative, and the escape keeps a
    # bracketed title from closing the link text early.
    assert links.to_markdown(f"see [[{ref}]] here", _resolve) == \
        r"see [Auth \[token\] expiry](/auth-tokens.md) here"


def test_an_unresolved_reference_becomes_plain_text_not_a_broken_link():
    # A ghost node is authoring intent inside cortex; exported as a dangling
    # link it is just a defect in somebody else's bundle.
    assert links.to_markdown("see [[other-ws/knowledge/gone]] here", _resolve) == \
        "see gone here"


def test_a_reference_inside_a_fence_is_an_example_and_is_left_alone():
    text = "a [[auth-tokens]]\n```\nb [[auth-tokens]]\n```\nc [[auth-tokens]]"
    out = links.to_markdown(text, _resolve).splitlines()
    assert out[2] == "b [[auth-tokens]]"
    assert out[0].startswith("a [Auth") and out[4].startswith("c [Auth")


def test_a_reference_inside_inline_code_is_syntax_not_a_reference():
    # Found on the real store: `[[...]]` is how three docs write *about* the
    # grammar, and rewriting it to `...` corrupts the sentence explaining it.
    assert links.to_markdown("the `[[...]]` grammar, and [[auth-tokens]]", _resolve) == \
        r"the `[[...]]` grammar, and [Auth \[token\] expiry](/auth-tokens.md)"


def test_a_titleless_doc_links_under_its_slug():
    assert links.to_markdown("[[x]]", lambda ref: ("x", "")) == "[x](/x.md)"


def test_an_empty_reference_is_not_a_reference():
    assert links.to_markdown("[[]] and [[ ]]", _resolve) == "[[]] and [[ ]]"


# ---- import: markdown -> [[wikilink]] ----

@pytest.mark.parametrize("target", [
    "/auth-tokens.md",          # bundle-absolute (§7's recommendation)
    "auth-tokens.md",           # relative
    "./auth-tokens.md",
    "concepts/auth-tokens.md",  # a nested bundle, flattened on the way in
])
def test_a_link_to_a_bundle_doc_becomes_a_wikilink(target):
    assert links.to_wikilinks(f"see [Tokens]({target}) here", _is_doc) == \
        "see [[knowledge/auth-tokens]] here"


@pytest.mark.parametrize("target", [
    "https://example.com/auth-tokens.md",   # external
    "#anchor",                              # in-page
    "/absent.md",                           # a doc this bundle does not hold
    "/data.csv",                            # not a concept
])
def test_every_other_link_is_left_exactly_as_it_was(target):
    text = f"see [Tokens]({target}) here"
    assert links.to_wikilinks(text, _is_doc) == text


def test_a_link_inside_a_fence_is_an_example_and_is_left_alone():
    text = "```\n[Tokens](/auth-tokens.md)\n```"
    assert links.to_wikilinks(text, _is_doc) == text


def test_a_link_inside_inline_code_is_syntax_and_is_left_alone():
    text = "write `[Tokens](/auth-tokens.md)` like [Tokens](/auth-tokens.md)"
    assert links.to_wikilinks(text, _is_doc) == \
        "write `[Tokens](/auth-tokens.md)` like [[knowledge/auth-tokens]]"


def test_two_links_on_one_line_both_translate():
    assert links.to_wikilinks("[a](/auth-tokens.md) [b](/token-refresh.md)",
                              _is_doc) == \
        "[[knowledge/auth-tokens]] [[knowledge/token-refresh]]"
