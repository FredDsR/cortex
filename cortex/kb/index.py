"""The derived catalog: `kb index`, and the §8 renderer `okf export` shares.

One read of a kb directory (`_doc_rows`) feeds three renderings: the flat
listing an agent reads on stdout, the OKF §8 group listing a bundle consumer
parses, and the cross-workspace dictionary. One reader so none of them can
disagree about what is in the directory or in what order.

Reads the store and writes the derived index; prints nothing. `cli.py` decides
what reaches a terminal.
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path

from cortex import atomic
from cortex import frontmatter as fm
from cortex import model
from cortex.kb.common import (INDEX_NAME, LEGACY_INDEX_NAME, md_escape,
                              more_notice)

def _doc_rows(dir_path: Path) -> list[tuple[str, str, str, str]]:
    """(type, slug, title, description) per non-index doc in DIR_PATH, ordered
    by lowercased type (untyped last) then slug.

    The single read of a kb directory. The flat stdout listing, the OKF §8
    index file, and the cross-workspace dictionary are three renderings of
    these rows, so none of them can disagree about what is in the directory or
    in what order."""
    rows = []
    if not dir_path.is_dir():
        return rows
    # The reservation is a property of the directory, not of the name: only
    # `knowledge/` holds files cortex derives, so `log.md` is reserved there and
    # an ordinary doc in `workbench/`. The bare `index.md` skip below is the
    # pre-existing one and stays as it was for every other kb directory.
    bundle = dir_path.name == "knowledge"
    for f in sorted(dir_path.glob("*.md")):
        if model.is_reserved(f.name) if bundle else f.name.lower() == "index.md":
            continue
        block, _ = fm.split(f.read_text(encoding="utf-8"))
        block = block or ""
        ty = fm.read_field(block, "type")
        title = fm.read_field(block, "title")
        desc = model.format_description(fm.read_field(block, "description"), title)
        rows.append((ty, f.stem, title, desc))
    rows.sort(key=lambda r: (r[0].lower() if r[0] else "~~~", r[1]))
    return rows

def _okf_entry(text: str, target: str, desc: str) -> str:
    """One OKF v0.2 §8 index entry: `* [Title](relative-url) - description`.

    The link text is the doc's title when it has one, but the URL always ends
    in `<slug>.md`, so the slug an agent needs for `[[wikilinks]]` stays on the
    line either way.

    A bracket in the title is escaped: unescaped, `title: [Design] rework`
    closes the link text early, which breaks the link for a bundle consumer and
    makes `cortex kb lint` read its own freshly derived index as hand-edited."""
    return f"* [{md_escape(text)}]({target}) - {desc}"
def _okf_heading(display_ty: str, first: bool) -> list[str]:
    """A §8 group heading, blank-line separated from what precedes it."""
    return ([] if first else [""]) + [f"## {display_ty or '(untyped)'}", ""]


def render_section(dir_path: Path, max_n: int | None, *, okf: bool = False) -> list[str]:
    """The rows of one kb directory, capped at max_n with a `... K more`
    notice. Flat (`<slug> [<type>] - <desc>`) by default: that is what an agent
    reads on stdout and what `cortex inject` emits. `okf=True` renders the same
    rows as §8 `## <type>` groups of markdown-link entries, which is the shape
    a bundle consumer parses. One function so the two can only ever differ in
    presentation, never in contents or order."""
    rows = _doc_rows(dir_path)
    if not rows:
        return []
    if not okf:
        out = [slug + (f" [{ty}]" if ty else "") + f" - {desc}"
               for ty, slug, _title, desc in rows[:max_n]]
        return out + more_notice(len(rows), max_n)
    out = []
    for display_ty, group in model.group_by_type(rows[:max_n], lambda r: r[0]):
        out += _okf_heading(display_ty, first=not out)
        out += [_okf_entry(title or slug, f"{slug}.md", desc)
                for _ty, slug, title, desc in group]
    return out + more_notice(len(rows), max_n)
def _knowledge_rows(kdir: Path, ws_name: str) -> list[tuple[str, str, str, str, str]]:
    """(type, slug, workspace, title, description) per non-index knowledge doc."""
    return [(ty, slug, ws_name, title, desc)
            for ty, slug, title, desc in _doc_rows(kdir)]
def render_all(workspaces_root: Path, max_n: int | None, *, okf: bool = False) -> list[str]:
    """Cross-workspace dictionary: `## <type>` sections (untyped last), each
    sorted by slug then workspace and capped per section. Scope is the global
    store's workspaces; repo-local `.cortex` stores are not included (they are
    per-repo, not part of the cross-workspace brain).

    `okf=True` renders §8 entries instead of flat lines. The URL is relative to
    `~/.cortex/knowledge/`, where the derived root index lives, so it resolves
    from the file that carries it."""
    rows: list[tuple[str, str, str, str, str]] = []
    if workspaces_root.is_dir():
        for ws in sorted(p for p in workspaces_root.iterdir() if p.is_dir()):
            rows += _knowledge_rows(ws / "knowledge", ws.name)
    lines: list[str] = []
    for display_ty, group in model.group_by_type(rows, lambda r: r[0]):
        entries = sorted(group, key=lambda r: (r[1], r[2]))   # slug, then workspace
        if okf:
            lines += _okf_heading(display_ty, first=not lines)
            lines += [_okf_entry(f"{title or slug} ({ws})",
                                 f"../workspaces/{ws}/knowledge/{slug}.md", desc)
                      for _ty, slug, ws, title, desc in entries[:max_n]]
        else:
            lines.append(f"## {display_ty if display_ty else '(untyped)'}")
            lines += [f"{slug} ({ws}) - {desc}"
                      for _ty, slug, ws, _title, desc in entries[:max_n]]
        lines += more_notice(len(entries), max_n)
    return lines
def _retire_legacy_index(kdir: Path) -> None:
    """Remove a pre-conformance `INDEX.md` so the directory holds one index.

    On a case-insensitive filesystem the two spellings are one file, so there
    is nothing to delete and a plain rewrite would leave git tracking the
    uppercase name forever. `git mv` through a third name is the only way to
    record the rename; outside a git repo the write still produces the right
    bytes under the right name and only the history stays silent."""
    legacy, current = kdir / LEGACY_INDEX_NAME, kdir / INDEX_NAME
    if not legacy.exists():
        return
    if not (current.exists() and legacy.samefile(current)):
        legacy.unlink()
        return
    tmp = "index.okf-rename.md"
    try:
        for src, dst in ((LEGACY_INDEX_NAME, tmp), (tmp, INDEX_NAME)):
            r = subprocess.run(["git", "mv", "-f", src, dst], cwd=kdir,
                               capture_output=True)
            if r.returncode != 0:
                break
    except OSError:
        pass
    if (kdir / tmp).exists():           # git took the first step and not the second
        os.replace(kdir / tmp, current)


def write_index(kdir: Path, lines: list[str]) -> Path:
    """Write the derived §8 index, then retire any legacy `INDEX.md`.

    Both happen before the caller's `sync_after`, because `cortex sync push`
    stages the whole store in one commit. Split across two commits, a `sync
    pull` on a second device resurrects the old name beside the new one.

    Write first, retire second, so an interrupted first `--write` after the
    rename leaves the old index rather than no index at all. On a
    case-insensitive filesystem the two names are one file, which
    `_retire_legacy_index` detects and renames instead of deleting, so the
    freshly written bytes survive that order too."""
    kdir.mkdir(parents=True, exist_ok=True)
    path = kdir / INDEX_NAME
    atomic.write_text(path, "\n".join(lines) + "\n", encoding="utf-8")
    _retire_legacy_index(kdir)
    return path
