#!/usr/bin/env python3
"""Convert legacy bold-pair fields in SUMMARY.md and tasks/*.md into YAML frontmatter.

Idempotent: skips files that already have frontmatter for all detected fields.
Default mode is dry-run; pass --apply to write.

Usage:
    migrate_to_frontmatter.py [--root PATH] [--apply] [--quiet]

Walks <root>/workspaces/*/sessions/*/SUMMARY.md and <root>/workspaces/*/sessions/*/tasks/*.md.
Also handles a repo-local store: if --root points at a `.work/` directory itself,
walks <root>/sessions/*/... directly.
"""
from __future__ import annotations
import argparse
import os
import re
import sys
from pathlib import Path

FM_DELIM = "---"
INLINE_RE = re.compile(r"^\*\*([^*:]+?)(?::\*\*|\*\*:)\s*(.*)$")
LINK_RE = re.compile(r"^\[([^\]]+)\]\(([^)]+)\)$")
BLOCKED_BY_RE = re.compile(r"^\s*\*?\*?\s*Blocked by", re.IGNORECASE)

# Bold-pair label -> (frontmatter key, optional companion-url key)
TASK_FIELDS = {
    "Status": ("status", None),
    "Started": ("started", None),
    "Branch": ("branch", None),
    "Ticket": ("ticket", "ticket_url"),
    "PR": ("pr", "pr_url"),
}
SUMMARY_FIELDS = {
    "Slug": ("slug", None),
    "Started": ("started", None),
    "Last updated": ("last_updated", None),
    "Session status": ("status", None),
    "Branch": ("branch", None),
    "Closed": ("closed", None),
}


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith(FM_DELIM + "\n"):
        return {}, text
    end = text.find("\n" + FM_DELIM + "\n", len(FM_DELIM) + 1)
    if end == -1:
        return {}, text
    block = text[len(FM_DELIM) + 1:end]
    body = text[end + 1 + len(FM_DELIM) + 1:]
    meta: dict = {}
    for line in block.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body


def extract_field_value(raw: str, url_key: str | None) -> dict:
    """Return {primary_key_value: ..., url_key_value: ...} from a bold-pair value."""
    m = LINK_RE.match(raw.strip())
    if m and url_key:
        text = m.group(1).lstrip("#").strip()
        url = m.group(2).strip()
        return {"value": text, "url": url}
    return {"value": raw.strip(), "url": None}


def convert_body(body: str, fields_map: dict) -> tuple[dict, str]:
    """Pull bold-pair fields out of body. Return (extracted_meta, new_body)."""
    extracted: dict = {}
    new_lines: list[str] = []
    for line in body.splitlines(keepends=True):
        # Don't strip the "Blocked by:" line; that one is structural body content.
        if BLOCKED_BY_RE.match(line):
            new_lines.append(line)
            continue
        m = INLINE_RE.match(line.rstrip("\n"))
        if not m:
            new_lines.append(line)
            continue
        label = m.group(1).strip()
        if label not in fields_map:
            new_lines.append(line)
            continue
        primary_key, url_key = fields_map[label]
        parts = extract_field_value(m.group(2), url_key)
        if parts["value"]:
            extracted.setdefault(primary_key, parts["value"])
        if url_key and parts["url"]:
            extracted.setdefault(url_key, parts["url"])
        # Drop the bold-pair line from the body.
    new_body = "".join(new_lines)
    # Collapse leading blank lines that result from removed bold-pair block.
    while new_body.startswith("\n"):
        new_body = new_body[1:]
    return extracted, new_body


def emit_frontmatter(meta: dict, key_order: list[str]) -> str:
    seen = set()
    lines = [FM_DELIM]
    for k in key_order:
        if k in meta:
            lines.append(f"{k}: {meta[k]}")
            seen.add(k)
    for k, v in meta.items():
        if k not in seen:
            lines.append(f"{k}: {v}")
    lines.append(FM_DELIM)
    lines.append("")  # trailing blank before body
    return "\n".join(lines) + "\n"


def process_file(path: Path, fields_map: dict, key_order: list[str]) -> tuple[str, str | None]:
    """Return (action, new_text). action in {'convert', 'skip', 'no-change', 'keep'}."""
    raw = path.read_text(encoding="utf-8")
    existing_meta, body = split_frontmatter(raw)
    extracted, new_body = convert_body(body, fields_map)
    if not extracted and existing_meta:
        return ("keep", None)  # already migrated, nothing extra to do
    if not extracted and not existing_meta:
        return ("no-change", None)
    merged = dict(extracted)
    # Existing frontmatter wins over freshly extracted bold-pair (in case both present).
    for k, v in existing_meta.items():
        merged[k] = v
    new_text = emit_frontmatter(merged, key_order) + new_body
    if new_text == raw:
        return ("no-change", None)
    return ("convert", new_text)


def iter_target_files(root: Path):
    """Yield (file_path, fields_map, key_order) for every SUMMARY.md and tasks/*.md."""
    # Layout 1: root/workspaces/<slug>/sessions/<sess>/SUMMARY.md
    workspaces = root / "workspaces"
    sessions_roots: list[Path] = []
    if workspaces.is_dir():
        for ws in sorted(workspaces.iterdir()):
            if (ws / "sessions").is_dir():
                sessions_roots.append(ws / "sessions")
    # Layout 2: root/sessions/<sess>/SUMMARY.md  (repo-local .work/)
    if (root / "sessions").is_dir():
        sessions_roots.append(root / "sessions")
    for sroot in sessions_roots:
        for sess in sorted(sroot.iterdir()):
            if not sess.is_dir():
                continue
            summary = sess / "SUMMARY.md"
            if summary.exists():
                yield (summary, SUMMARY_FIELDS,
                       ["slug", "started", "last_updated", "status", "branch", "github", "closed"])
            tasks = sess / "tasks"
            if tasks.is_dir():
                for t in sorted(tasks.glob("*.md")):
                    yield (t, TASK_FIELDS,
                           ["status", "started", "ticket", "ticket_url",
                            "pr", "pr_url", "branch"])


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=os.path.expanduser("~/.work"),
                   help="Root to scan. Default: ~/.work")
    p.add_argument("--apply", action="store_true",
                   help="Actually write changes. Without this flag, runs as dry-run.")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        print(f"migrate: root does not exist: {root}", file=sys.stderr)
        return 2

    counts = {"convert": 0, "no-change": 0, "keep": 0, "error": 0}
    for path, fmap, key_order in iter_target_files(root):
        try:
            action, new_text = process_file(path, fmap, key_order)
        except Exception as exc:  # pragma: no cover  (defensive)
            counts["error"] += 1
            print(f"ERROR  {path}: {exc}", file=sys.stderr)
            continue
        counts[action] = counts.get(action, 0) + 1
        if action == "convert":
            if not args.quiet:
                print(f"{'WRITE ' if args.apply else 'WOULD '} {path}")
            if args.apply and new_text is not None:
                path.write_text(new_text, encoding="utf-8")
        elif action == "keep" and not args.quiet:
            print(f"KEEP   {path} (already has frontmatter)")
        elif action == "no-change" and not args.quiet:
            print(f"SKIP   {path} (no fields to migrate)")

    print()
    summary = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
    mode = "applied" if args.apply else "dry-run"
    print(f"migrate ({mode}): {summary or 'nothing scanned'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
