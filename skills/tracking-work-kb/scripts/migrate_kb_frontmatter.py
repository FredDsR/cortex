#!/usr/bin/env python3
"""One-shot migration for existing ~/.work knowledge/workbench docs.

- Normalizes frontmatter: backfills `updated` (= created) and enforces the
  canonical field order, line-preservingly (no yaml.dump / re-quoting).
- Regenerates knowledge/INDEX.md banner text to `cortex kb index`.
- Reports (does NOT edit) `work-kb`/`work-viz` references in doc prose.
Dry-run by default; --write applies frontmatter + banner edits.
"""
from __future__ import annotations
import sys, re, argparse
from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None

CANON = ["title", "type", "author", "created", "updated", "description"]
STALE = re.compile(r"\bwork-(kb|viz)\b")
_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):")


def _split(text):
    """Return (fm_lines, body_lines) or (None, None) if no leading frontmatter."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, None
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        return None, None
    return lines[1:close], lines[close + 1:]


def normalize_frontmatter(text):
    """Return (new_text or None, changed). None when there is no frontmatter."""
    fm_lines, body_lines = _split(text)
    if fm_lines is None:
        return None, False
    if yaml is not None:
        try:
            yaml.safe_load("\n".join(fm_lines))
        except Exception:
            return None, False  # malformed; skip
    kv, order = {}, []
    for ln in fm_lines:
        mm = _KEY.match(ln)
        if mm:
            k = mm.group(1)
            kv[k] = ln
            if k not in order:
                order.append(k)
    if "updated" not in kv and "created" in kv:
        # Copy everything after the "created" key (the ": <value>" part) verbatim.
        kv["updated"] = "updated" + kv["created"][len("created"):]
    elif "updated" not in kv:
        return None, False  # nothing to anchor an updated to; leave alone
    new_fm = [kv[k] for k in CANON if k in kv]
    new_fm += [kv[k] for k in order if k not in CANON]  # preserve unknown keys
    if new_fm == fm_lines:
        return text, False
    new_text = "\n".join(["---"] + new_fm + ["---"] + body_lines)
    return new_text, True


def stale_refs_in_body(text):
    _, body_lines = _split(text)
    if body_lines is None:
        body_lines = text.split("\n")
    out = []
    for i, ln in enumerate(body_lines, 1):
        if STALE.search(ln):
            out.append((i, ln))
    return out


def _iter_docs(root: Path):
    for ws in sorted(p for p in root.iterdir() if p.is_dir()):
        kd = ws / "knowledge"
        if kd.is_dir():
            yield from sorted(kd.glob("*.md"))
        sess = ws / "sessions"
        if sess.is_dir():
            for s in sorted(p for p in sess.iterdir() if p.is_dir()):
                wb = s / "workbench"
                if wb.is_dir():
                    yield from sorted(wb.glob("*.md"))


def main(argv):
    ap = argparse.ArgumentParser(prog="migrate_kb_frontmatter")
    ap.add_argument("--root", default=str(Path.home() / ".work" / "workspaces"))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: root not found: {root}", file=sys.stderr)
        return 1

    normalized = banners = skipped = 0
    prose = []
    for doc in _iter_docs(root):
        text = doc.read_text(encoding="utf-8")
        if doc.name.lower() == "index.md":
            new = text.replace("work-kb index", "cortex kb index")
            if new != text:
                banners += 1
                if args.write:
                    doc.write_text(new, encoding="utf-8")
            continue
        new, changed = normalize_frontmatter(text)
        if changed:
            normalized += 1
            if args.write:
                doc.write_text(new, encoding="utf-8")
        else:
            skipped += 1
        for lineno, line in stale_refs_in_body(text):
            prose.append((doc, lineno, line.strip()))

    mode = "wrote" if args.write else "would change (dry-run)"
    print(f"{mode}: normalized {normalized} docs, {banners} INDEX banners; "
          f"{skipped} already current; {len(prose)} prose references to review")
    for doc, lineno, line in prose:
        print(f"  {doc}:{lineno}: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
