"""`cortex kb lint --fix`: the only writer in this package.

Deliberately narrow. It repairs a broken reference ONLY when the target it
names exists elsewhere under an unambiguous address (`checks._repair` decides
that), so the edit changes an address and never a claim.
"""
from __future__ import annotations
import re
from pathlib import Path

from cortex import atomic
from cortex.errors import CortexError
from cortex.lint.checks import FENCE

# Boundary characters of an address token, used to bound the `--fix`
# replacement so `task-foo` never matches inside `task-foobar`.
_ADDR_CHAR = r"[A-Za-z0-9/_-]"
# The lines on which an unbracketed slug is a reference rather than a word:
# the parser's own typed body labels, and the frontmatter relation keys. Kept in
# the same order and spelling as cortex/parser.py's _BODY_REL_RE / _FM_KEY_TO_KIND.
_REL_LINE = re.compile(
    r"^\s*(?:Blocked by|Related to|Follows)\s*:|^(?:blocked_by|related_to|follows)\s*:",
    re.IGNORECASE)


def _replace_outside_fences(text: str, pairs) -> tuple[str, int]:
    """Rewrite each `raw` as `fix` where the text is structurally a reference.

    Two forms, and only two. Inside brackets anywhere (`[task-foo]`,
    `[[knowledge/foo]]`), and bare on a line that is a relation: a body
    `Related to:` / `Blocked by:` / `Follows:` line, or a frontmatter
    `related_to:` / `blocked_by:` / `follows:` key, which is where the parser
    reads a comma-separated list of unbracketed slugs.

    Anchoring matters. A slug is also an ordinary noun phrase, so an
    unrestricted bounded replacement rewrites prose: a doc holding both
    `[retry-policy]` and the sentence "the retry-policy changed" would come
    back saying "the knowledge/retry-policy changed". Rewriting an address is
    the contract; rewriting a sentence is not."""
    bracketed = [(re.compile(rf"\[{re.escape(raw)}\]"), fix) for raw, fix in pairs]
    bare = [(re.compile(rf"(?<!{_ADDR_CHAR}){re.escape(raw)}(?!{_ADDR_CHAR})"), fix)
            for raw, fix in pairs]
    out, in_fence, total = [], False, 0
    for line in text.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence:
            for pat, fix in bracketed:
                line, n = pat.subn(lambda _m, f=fix: f"[{f}]", line)
                total += n
            if _REL_LINE.match(line):
                for pat, fix in bare:
                    line, n = pat.subn(lambda _m, f=fix: f, line)
                    total += n
        out.append(line)
    return "\n".join(out), total


def apply_fixes(findings: list) -> tuple[list, list]:
    """Rewrite repairable references in place. Returns (applied, files written).

    The replacement lands on the authored forms and nowhere else: bracketed
    anywhere, bare only on a relation line (see _replace_outside_fences).
    Fenced blocks are skipped for the same reason the scanner skips them: what
    is in one is an example, not a reference.

    One reference at a time, so `applied` names the references that were really
    rewritten. Grouping the whole file into a single pass would report a
    reference as fixed on the strength of a sibling's replacement -- and with
    `--strict` that turns a still-broken reference into exit 0."""
    by_path: dict = {}
    for f in findings:
        if f.check == "broken-ref" and f.fix and f.path is not None:
            by_path.setdefault(Path(f.path), []).append(f)
    applied, written = [], []
    for path, group in sorted(by_path.items()):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            raise CortexError(f"cannot read {path}: {e}")
        new = text
        done = []
        for f in group:
            new, n = _replace_outside_fences(new, [(f.raw, f.fix)])
            if n:
                done.append(f)
        if not done or new == text:
            continue
        atomic.write_text(path, new, encoding="utf-8")
        written.append(path)
        applied.extend(done)
    return applied, written
