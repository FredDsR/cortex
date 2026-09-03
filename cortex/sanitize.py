"""Strip invisible and control characters out of text cortex did not author.

`kb ingest` reads a codebase that may be a dependency, a vendored spec, or
something nobody on the team wrote. Extracted strings land in `description:`,
`description:` is what `cortex inject here` emits into the `<cortex-index>`
block, and that block reaches a fresh agent at SessionStart before the user has
said anything. It is the family's one sanctioned auto-injection path, so it is
the one that most deserves scrutiny of what it lets through.

A right-to-left override or a zero-width run inside a description renders as
something other than what it is, in a block the agent treats as trusted
orientation. `re.sub(r"\\s+", " ", s)` does not touch either: they are not
whitespace to collapse and not whitespace to strip.

Scoped to the ingest path on purpose. Sanitizing in `frontmatter.emit()` would
rewrite a person's own notes, and cortex exists to preserve those byte for byte.

Pure (stdlib only).
"""
from __future__ import annotations
import unicodedata

# Named explicitly so the ones that motivated this are legible at a glance,
# and so the set holds even if a future Unicode release recategorizes one.
_EXPLICIT = frozenset(
    list(range(0x200B, 0x2010))         # ZWSP, ZWNJ, ZWJ, LRM, RLM
    + list(range(0x202A, 0x202F))       # LRE, RLE, PDF, LRO, RLO
    + list(range(0x2066, 0x206A))       # LRI, RLI, FSI, PDI
    + [0xFEFF]                          # ZWNBSP / BOM
)

# Cf format, Co private use, Cn unassigned: the three the threat model names.
# Cs (lone surrogates) and Cc (C0/C1 controls) join them because they are the
# same problem on the same path: `json.loads` accepts a "\\ud800" escape and the
# resulting string raises on utf-8 encode, and a bare ESC in a description is an
# ANSI sequence in every terminal that prints `cortex kb index`.
_STRIP = frozenset(("Cc", "Cf", "Co", "Cs", "Cn"))

# Kept out of the Cc sweep so sanitize() is safe on multi-line text; callers
# that want a single line collapse whitespace themselves.
_KEEP = frozenset("\t\n\r")

# NFKC can expand one codepoint into several, and dropping a codepoint can
# enable a composition that was previously blocked, so one pass is not
# necessarily a fixpoint. Bounded so a pathological input cannot spin.
_MAX_PASSES = 8


def _once(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(
        ch for ch in normalized
        if ch in _KEEP
        or (ord(ch) not in _EXPLICIT and unicodedata.category(ch) not in _STRIP)
    )


def sanitize(text) -> str:
    """Return TEXT with invisible, bidi-control, and control characters removed
    and NFKC-normalized, iterated to a bounded fixpoint."""
    s = str(text)
    for _ in range(_MAX_PASSES):
        nxt = _once(s)
        if nxt == s:
            break
        s = nxt
    return s
