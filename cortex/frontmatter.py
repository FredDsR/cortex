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


def scalar(v: str) -> str:
    """Render a value as a safe YAML scalar (plain when unambiguous, else a
    double-quoted string with backslash and double-quote escaped). Inverse of
    read_field()."""
    if v and _SAFE.match(v):
        return v
    v = v.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{v}"'


def emit(fields: dict, body: str) -> str:
    """Build a full doc (`---` frontmatter + blank line + body), matching
    work-kb emit_doc byte layout. `author`/`created`/`updated` must be present;
    `title`/`type`/`description` are emitted only when truthy."""
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
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body


def split_lines(text: str):
    """Locate leading `---`...`---` frontmatter. Return (fm_lines, body_lines,
    close_idx) using the raw `text.split("\\n")` slices (no trailing-newline or
    separator normalization), or (None, None, None) when absent. The single
    boundary splitter for the family: `split()` (emit-cycle) and the one-shot kb
    migrator both build on it. Boundary match is exact `---`."""
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return None, None, None
    close = next((i for i in range(1, len(lines)) if lines[i] == "---"), None)
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
