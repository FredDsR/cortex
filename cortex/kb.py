"""kb commands (new / update / index / ingest) for the cortex engine.

Ports the former skills/cortex-kb bash `work-kb` bin onto the shared core
(cortex.frontmatter + cortex.store). Behavior-preserving: same frontmatter
bytes, exit codes, and messages.
"""
from __future__ import annotations
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

from cortex import atomic
from cortex import frontmatter as fm
from cortex import model
from cortex import store
from cortex.errors import CortexError

AUTHOR_DEFAULT = "agent"
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# The documented `type` vocabulary (skills/cortex-kb/SKILL.md, "type
# vocabulary"). Still a convention rather than an enum -- a custom value is
# accepted without error -- so this exists only to name the canonical set in
# the error a typeless `kb new knowledge` raises.
TYPE_VOCABULARY = ("Decision", "Design", "Reference", "Runbook",
                   "Investigation", "Convention", "Comparison")

# OKF v0.2 §8 reserves lowercase `index.md` for a bundle's index. `INDEX.md` is
# what cortex derived before conformance and is retired on the next `--write`.
INDEX_NAME = "index.md"
LEGACY_INDEX_NAME = "INDEX.md"


def today() -> str:
    return datetime.date.today().isoformat()


def _home() -> Path:
    return Path(os.environ.get("HOME") or str(Path.home()))


def _validate_slug(slug: str) -> None:
    if not _SLUG.match(slug):
        raise CortexError(f"invalid slug: '{slug}' (must match [a-z0-9][a-z0-9-]*)")


def parse_max(value, flag: str = "--max") -> int:
    """Validate --max like bash did (^[0-9]+$ or die, exit 1). `flag` names the
    option in the error, so a caller reusing this for another numeric flag does
    not report a bad --stale-days as a bad --max."""
    if not re.fullmatch(r"[0-9]+", str(value)):
        raise CortexError(f"{flag} must be a non-negative integer")
    return int(value)


def _resolve_author(args) -> str:
    if args.author is not None:
        a = args.author
    else:
        a = "human" if args.open else AUTHOR_DEFAULT
    if a not in ("human", "agent"):
        raise CortexError("author must be 'human' or 'agent'")
    return a


def _resolve_path(args, kind: str) -> Path:
    ws_root = store.resolve_workspace(args.workspace, home=_home(), cwd=Path.cwd())
    if kind == "knowledge":
        return ws_root / "knowledge" / f"{args.slug}.md"
    sess = store.resolve_session(ws_root, args.session)
    return ws_root / "sessions" / sess / "workbench" / f"{args.slug}.md"


def _body_set(args) -> bool:
    return args.body is not None or args.body_from is not None


def _read_body(args, *, allow_stdin: bool) -> str:
    if args.body:                       # non-empty --body wins (bash: [[ -n ]])
        return args.body
    if args.body_from:
        if args.body_from == "-":
            return sys.stdin.read()
        try:
            return Path(args.body_from).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise CortexError(f"cannot read --body-from {args.body_from}: {e}")
    if allow_stdin and not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def sync_after(verb: str, kind: str, slug: str) -> None:
    # Best-effort: cortex.sync.push is a no-op when sync is not enabled.
    from cortex import sync
    try:
        sync.push(f"track(kb): {verb} {kind} {slug}", home=_home())
    except Exception:
        pass


def _maybe_open(args, path: Path) -> None:
    # bash exec's $EDITOR; we spawn+wait so an in-process caller survives.
    if args.open:
        editor = os.environ.get("EDITOR", "vi")
        try:
            subprocess.run([editor, str(path)], check=False)
        except OSError as e:
            raise CortexError(f"cannot launch editor '{editor}': {e}")


def _require_type(args) -> None:
    """OKF v0.2 §11 makes `type` the one required frontmatter field, and
    `knowledge/` is what an OKF bundle is made of. `workbench/` is exempt: it is
    session-scoped, dies with the session, and is never exported.

    `update` is exempt too. A store written before this rule still holds
    untyped docs, and refusing to touch one is refusing to fix it."""
    if args.kind == "knowledge" and not (args.type or "").strip():
        raise CortexError(
            "knowledge docs require --type (OKF v0.2 §11 makes it the one "
            "required field). Canonical values: "
            + ", ".join(TYPE_VOCABULARY) + "; custom values are accepted.")


def cmd_new(args) -> int:
    _validate_slug(args.slug)
    _require_type(args)
    author = _resolve_author(args)
    path = _resolve_path(args, args.kind)
    if path.exists():
        raise CortexError(f"{path} already exists")
    body = _read_body(args, allow_stdin=True)
    d = today()
    fields = {"title": args.title or "", "type": args.type or "", "author": author,
              "created": d, "updated": d, "description": args.description or ""}
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic.write_text(path, fm.emit(fields, body), encoding="utf-8")
    print(path)
    sync_after("new", args.kind, args.slug)
    _maybe_open(args, path)
    return 0


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
    for f in sorted(dir_path.glob("*.md")):
        if f.name.lower() == INDEX_NAME:
            continue                       # matches INDEX.md and index.md alike
        block, _ = fm.split(f.read_text(encoding="utf-8"))
        block = block or ""
        ty = fm.read_field(block, "type")
        title = fm.read_field(block, "title")
        desc = model.format_description(fm.read_field(block, "description"), title)
        rows.append((ty, f.stem, title, desc))
    rows.sort(key=lambda r: (r[0].lower() if r[0] else "~~~", r[1]))
    return rows


def _more_notice(total: int, max_n: int) -> list[str]:
    return [f"... {total - max_n} more (raise --max)"] if total > max_n else []


def _okf_entry(text: str, target: str, desc: str) -> str:
    """One OKF v0.2 §8 index entry: `* [Title](relative-url) - description`.

    The link text is the doc's title when it has one, but the URL always ends
    in `<slug>.md`, so the slug an agent needs for `[[wikilinks]]` stays on the
    line either way."""
    return f"* [{text}]({target}) - {desc}"


def _okf_heading(display_ty: str, first: bool) -> list[str]:
    """A §8 group heading, blank-line separated from what precedes it."""
    return ([] if first else [""]) + [f"## {display_ty or '(untyped)'}", ""]


def _render_section(dir_path: Path, max_n: int, *, okf: bool = False) -> list[str]:
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
        return out + _more_notice(len(rows), max_n)
    out = []
    for display_ty, group in model.group_by_type(rows[:max_n], lambda r: r[0]):
        out += _okf_heading(display_ty, first=not out)
        out += [_okf_entry(title or slug, f"{slug}.md", desc)
                for _ty, slug, title, desc in group]
    return out + _more_notice(len(rows), max_n)


def _knowledge_rows(kdir: Path, ws_name: str) -> list[tuple[str, str, str, str, str]]:
    """(type, slug, workspace, title, description) per non-index knowledge doc."""
    return [(ty, slug, ws_name, title, desc)
            for ty, slug, title, desc in _doc_rows(kdir)]


def _render_all(workspaces_root: Path, max_n: int, *, okf: bool = False) -> list[str]:
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
        lines += _more_notice(len(entries), max_n)
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


def _write_index(kdir: Path, lines: list[str]) -> Path:
    """Write the derived §8 index, retiring any legacy `INDEX.md` first.

    Both happen before the caller's `sync_after`, because `cortex sync push`
    stages the whole store in one commit. Split across two commits, a `sync
    pull` on a second device resurrects the old name beside the new one."""
    kdir.mkdir(parents=True, exist_ok=True)
    _retire_legacy_index(kdir)
    path = kdir / INDEX_NAME
    atomic.write_text(path, "\n".join(lines) + "\n", encoding="utf-8")
    return path


def cmd_index(args) -> int:
    max_n = parse_max(args.max)
    if args.workspace == "all":
        workspaces_root = _home() / ".cortex" / "workspaces"
        if args.write:
            out = [
                "<!-- generated by cortex kb index --workspace=all; do not edit. "
                "regenerate with: cortex kb index --workspace=all --write -->",
                "# Knowledge index (all workspaces)", "",
            ] + _render_all(workspaces_root, max_n, okf=True)
            path = _write_index(_home() / ".cortex" / "knowledge", out)
            print(path)
            sync_after("index", "knowledge", "INDEX")
            return 0
        for ln in _render_all(workspaces_root, max_n):
            print(ln)
        return 0
    ws_root = store.resolve_workspace(args.workspace, home=_home(), cwd=Path.cwd())
    kdir = ws_root / "knowledge"

    if args.write:
        lines = [
            "<!-- generated by cortex kb index; do not edit. regenerate with: cortex kb index --write -->",
            "# Knowledge index", "",
        ] + _render_section(kdir, max_n, okf=True)
        print(_write_index(kdir, lines))
        sync_after("index", "knowledge", "INDEX")
        return 0

    print("## knowledge")
    for ln in _render_section(kdir, max_n):
        print(ln)

    if args.session:
        sess = store.resolve_session(ws_root, args.session)
    else:
        try:
            sess = store.resolve_session(ws_root, "")
        except store.StoreError:
            sess = ""
    if sess:
        wdir = ws_root / "sessions" / sess / "workbench"
        if wdir.is_dir():
            print(f"\n## workbench ({sess})")
            for ln in _render_section(wdir, max_n):
                print(ln)
    return 0


def cmd_update(args) -> int:
    _validate_slug(args.slug)
    path = _resolve_path(args, args.kind)
    if not path.exists():
        raise CortexError(f"{path} not found")
    block, ex_body = fm.split(path.read_text(encoding="utf-8"))
    if block is None:
        raise CortexError(f"{path} has malformed frontmatter")

    ex = {k: fm.read_field(block, k) for k in
          ("title", "type", "description", "author", "created")}
    # Keys this command does not model (ingest provenance, a ticket, anything a
    # user added by hand) ride through untouched instead of being dropped.
    extra = fm.unknown_lines(block)

    title = args.title if args.title is not None else ex["title"]
    typ = args.type if args.type is not None else ex["type"]
    desc = args.description if args.description is not None else ex["description"]
    if args.author is not None:
        if args.author not in ("human", "agent"):
            raise CortexError("author must be 'human' or 'agent'")
        author = args.author
    else:
        author = ex["author"] or AUTHOR_DEFAULT
    created = ex["created"] or today()

    # When a body flag is given, bash read_body still falls back to stdin (so
    # `--body '' | ...` takes stdin); the pure-touch path (no body flag) never
    # reads stdin and keeps the existing body.
    body = _read_body(args, allow_stdin=True) if _body_set(args) else ex_body
    fields = {"title": title, "type": typ, "author": author,
              "created": created, "updated": today(), "description": desc}
    atomic.write_text(path, fm.emit(fields, body, extra=extra), encoding="utf-8")
    print(path)
    sync_after("update", args.kind, args.slug)
    _maybe_open(args, path)
    return 0
