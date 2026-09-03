"""The single frontmatter reader/writer for the cortex engine.

Ported from the retired bash work-kb (emit_doc, _yaml_scalar, split_fm,
fm_field) with byte-identical output; it is now the sole frontmatter
reader/writer/splitter in the family. Pure (stdlib only).
"""
from __future__ import annotations
import re

# Canonical frontmatter field order (authoritative here for the engine).
CANON = ["title", "type", "author", "created", "updated", "description"]

# `\Z` (not `$`) so a trailing newline does NOT count as "safe": Python's `$`
# matches just before a final newline, but bash ERE `$` is true end-of-string.
_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./() -]*\Z")

# A frontmatter line that opens a key. Anything else (a list item, a nested
# mapping, a comment) continues whichever key preceded it.
_KEY = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*):")


def scalar(v: str) -> str:
    """Render a value as a safe YAML scalar (plain when unambiguous, else a
    double-quoted string with backslash and double-quote escaped). Inverse of
    read_field()."""
    if v and _SAFE.match(v):
        return v
    v = v.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{v}"'


def unknown_lines(fm_block: str) -> list:
    """Return the raw lines of FM_BLOCK belonging to keys outside CANON, in
    their original order and bytes (continuation lines follow their key).

    Lines are preserved verbatim rather than parsed into values: a non-scalar
    the engine never authored (`blocked_by: [task-foo, task-bar]`, a block-style
    list) survives a round trip unchanged, where re-rendering it through
    scalar() would quote it into a string. Feed the result to emit(extra=...)."""
    if not fm_block:
        return []
    out = []
    keep = True     # lines before the first key (comments) are not ours to drop
    for line in fm_block.split("\n"):
        m = _KEY.match(line)
        if m:
            keep = m.group(1) not in CANON
        if keep:
            out.append(line)
    return out


def emit(fields: dict, body: str, extra=None) -> str:
    """Build a full doc (`---` frontmatter + blank line + body), matching
    work-kb emit_doc byte layout. `author`/`created`/`updated` must be present;
    `title`/`type`/`description` are emitted only when truthy.

    `extra` is an optional list of already-rendered frontmatter lines (from
    unknown_lines()) written verbatim after the canonical block. Omitting it,
    or passing an empty list, leaves the output byte-identical to emit_doc."""
    lines = ["---"]
    if fields.get("title"):
        lines.append(f"title: {scalar(fields['title'])}")
    if fields.get("type"):
        lines.append(f"type: {scalar(fields['type'])}")
    lines.append(f"author: {fields['author']}")
    lines.append(f"created: {fields['created']}")
    lines.append(f"updated: {fields['updated']}")
    if fields.get("description"):
        lines.append(f"description: {scalar(fields['description'])}")
    if extra:
        lines.extend(extra)
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body


def split_lines(text: str, *, tolerant: bool = False):
    """Locate leading `---`...`---` frontmatter. Return (fm_lines, body_lines,
    close_idx) using the raw `text.split("\\n")` slices (no trailing-newline or
    separator normalization), or (None, None, None) when absent. The single
    boundary splitter for the family: `split()` (emit-cycle) and the one-shot kb
    migrator both build on it.

    Default fence match is exact `---` (what emit() writes, and what the engine
    relies on for byte parity). `tolerant=True` also accepts a whitespace-padded
    fence (`--- `); the migrator opts in for legacy hand-edited docs."""
    def _is_fence(s: str) -> bool:
        return s.strip() == "---" if tolerant else s == "---"

    lines = text.split("\n")
    if not lines or not _is_fence(lines[0]):
        return None, None, None
    close = next((i for i in range(1, len(lines)) if _is_fence(lines[i])), None)
    if close is None:
        return None, None, None
    return lines[1:close], lines[close + 1:], close


def split(text: str):
    """Return (fm_block, body) or (None, None) if there is no leading
    `---`...`---` frontmatter. Strips the single blank line emit() inserts."""
    fm_lines, body_lines, _ = split_lines(text)
    if fm_lines is None:
        return None, None
    block = "\n".join(fm_lines)
    body = "\n".join(body_lines)
    # Match bash split_fm: FM_BODY is captured via `$(...)`, which strips ALL
    # trailing newlines; then one leading blank (emit()'s separator) is dropped.
    body = body.rstrip("\n")
    if body.startswith("\n"):
        body = body[1:]
    return block, body


def read_field(fm_block: str, key: str) -> str:
    """Return the scalar value of KEY (empty if absent), unwrapping a
    double-quoted value (inverse of scalar())."""
    raw = ""
    pat = re.compile(r"^" + re.escape(key) + r": ?(.*)$")
    for line in fm_block.split("\n"):
        m = pat.match(line)
        if m:
            raw = m.group(1)
            break
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        raw = raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return raw
