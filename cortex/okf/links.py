"""Translate references between cortex's `[[wikilinks]]` and OKF markdown links.

#50 kept `[[wikilinks]]` in the store on purpose: emitting markdown links
beside them would mean two link grammars to keep in sync forever. The cost is
that an external consumer reading an exported `knowledge/` sees the concepts
and none of the edges, because every `[[foo]]` is prose to them.

That tension resolves if the translation happens once, at a boundary, instead
of continuously, in the store. This module is that boundary, and it is pure:
callers supply the lookup that says what the bundle actually holds.

Both directions skip fenced blocks and inline code, for the reason
`cortex/parser.py` does: what is inside one is an example of the syntax, not a
use of it, and rewriting it corrupts the sentence explaining the syntax. That
is not hypothetical -- three docs in a real store write about the `[[...]]`
grammar in inline code, and a scan that does not stop at a backtick turns each
of them into `...`.
"""
from __future__ import annotations
import re

from cortex.kb import _md_escape
from cortex.lint.checks import FENCE

# `[[...]]` with no nested bracket. Single-bracket `[slug]` mentions are left
# alone: they address tasks and workbench docs, and a bundle holds neither.
_WIKILINK = re.compile(r"\[\[([^\[\]]+)\]\]")

# A markdown inline link. The label stops at the first unescaped `]` rather
# than running greedy, so two links on one line stay two links -- and it steps
# over a backslash-escaped one, because `to_markdown` writes exactly that when
# a title holds a bracket, and a link cortex itself exported has to be readable
# on the way back in.
_MD_LINK = re.compile(r"\[((?:[^\[\]\\]|\\.)*)\]\(([^)\s]+)\)")

# An inline code span, the same shape `parser._CODE_SPAN_RE` skips.
_CODE_SPAN = re.compile(r"`[^`\n]*`")


def _rewrite(text: str, pattern, repl) -> str:
    """PATTERN.sub(REPL) over TEXT, everywhere except fenced blocks and inline
    code spans."""
    def _line(line: str) -> str:
        out, pos = [], 0
        for m in _CODE_SPAN.finditer(line):
            out.append(pattern.sub(repl, line[pos:m.start()]))
            out.append(m.group(0))
            pos = m.end()
        out.append(pattern.sub(repl, line[pos:]))
        return "".join(out)

    out, in_fence = [], False
    for line in text.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        out.append(line if in_fence else _line(line))
    return "\n".join(out)


def to_markdown(text: str, resolve) -> str:
    """Rewrite `[[ref]]` for export. RESOLVE(ref) returns (slug, title) for a
    doc the bundle holds, or None.

    A resolved reference becomes `[Title](/slug.md)`: §7 recommends
    bundle-absolute over relative, and every concept sits at the bundle root.

    An unresolved one becomes plain text, not a dangling link. A ghost node is
    authoring intent inside cortex, where `cortex query neighbors` shows it and
    `kb lint --check broken-ref` reports it; exported as a broken link it is
    just a defect in somebody else's bundle. The text kept is the reference's
    last segment, which is the name the author wrote; the `knowledge/` or
    workspace qualifier in front of it addresses a store the reader does not
    have."""
    def _one(m):
        ref = m.group(1).strip()
        if not ref:
            return m.group(0)
        hit = resolve(ref)
        if hit is None:
            return ref.rsplit("/", 1)[-1]
        slug, title = hit
        return f"[{_md_escape(title or slug)}](/{slug}.md)"

    return _rewrite(text, _WIKILINK, _one)


def to_wikilinks(text: str, is_doc) -> str:
    """Rewrite markdown links for import. IS_DOC(stem) says whether the bundle
    holds that concept.

    Only links between concepts are translated. An external URL, an in-page
    anchor, a link to a non-`.md` asset, and a link to a `.md` file this import
    did not take are all left exactly as they were: rewriting one would turn a
    working link into a ghost reference that resolves to nothing.

    A nested bundle flattens on the way in, because `knowledge/` is flat, so
    the concept is addressed by its stem."""
    def _one(m):
        target = m.group(2)
        if "://" in target or target.startswith(("#", "mailto:")):
            return m.group(0)
        name = target.split("#", 1)[0].rsplit("/", 1)[-1]
        if not name.endswith(".md"):
            return m.group(0)
        stem = name[:-3]
        return f"[[knowledge/{stem}]]" if is_doc(stem) else m.group(0)

    return _rewrite(text, _MD_LINK, _one)
