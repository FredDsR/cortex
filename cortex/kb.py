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


def today() -> str:
    return datetime.date.today().isoformat()


def _home() -> Path:
    return Path(os.environ.get("HOME") or str(Path.home()))


def _validate_slug(slug: str) -> None:
    if not _SLUG.match(slug):
        raise CortexError(f"invalid slug: '{slug}' (must match [a-z0-9][a-z0-9-]*)")


def parse_max(value) -> int:
    """Validate --max like bash did (^[0-9]+$ or die, exit 1)."""
    if not re.fullmatch(r"[0-9]+", str(value)):
        raise CortexError("--max must be a non-negative integer")
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


def cmd_new(args) -> int:
    _validate_slug(args.slug)
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


def _render_section(dir_path: Path, max_n: int) -> list[str]:
    """One line per doc `<slug> [<type>] - <desc>`, ordered by lowercased type
    (untyped last) then slug, capped at max_n with a `... K more` notice."""
    if not dir_path.is_dir():
        return []
    rows = []
    for f in sorted(dir_path.glob("*.md")):
        if f.name.lower() == "index.md":
            continue
        block, _ = fm.split(f.read_text(encoding="utf-8"))
        block = block or ""
        ty = fm.read_field(block, "type")
        desc = model.format_description(fm.read_field(block, "description"),
                                        fm.read_field(block, "title"))
        render = f.stem + (f" [{ty}]" if ty else "") + f" - {desc}"
        rows.append((ty.lower() if ty else "~~~", f.stem, render))
    if not rows:
        return []
    total = len(rows)
    rows.sort(key=lambda r: (r[0], r[1]))
    out = [r[2] for r in rows[:max_n]]
    if total > max_n:
        out.append(f"... {total - max_n} more (raise --max)")
    return out


def _knowledge_rows(kdir: Path, ws_name: str) -> list[tuple[str, str, str, str]]:
    """(type, slug, workspace, description) per non-index knowledge doc."""
    rows = []
    if not kdir.is_dir():
        return rows
    for f in sorted(kdir.glob("*.md")):
        if f.name.lower() == "index.md":
            continue
        block, _ = fm.split(f.read_text(encoding="utf-8"))
        block = block or ""
        ty = fm.read_field(block, "type")
        desc = model.format_description(fm.read_field(block, "description"),
                                        fm.read_field(block, "title"))
        rows.append((ty, f.stem, ws_name, desc))
    return rows


def _render_all(workspaces_root: Path, max_n: int) -> list[str]:
    """Cross-workspace dictionary: `## <type>` sections (untyped last), each
    `<slug> (<ws>) - <desc>` sorted by slug then workspace, capped per section.
    Scope is the global store's workspaces; repo-local `.cortex` stores are not
    included (they are per-repo, not part of the cross-workspace brain)."""
    rows: list[tuple[str, str, str, str]] = []
    if workspaces_root.is_dir():
        for ws in sorted(p for p in workspaces_root.iterdir() if p.is_dir()):
            rows += _knowledge_rows(ws / "knowledge", ws.name)
    lines: list[str] = []
    for display_ty, group in model.group_by_type(rows, lambda r: r[0]):
        lines.append(f"## {display_ty if display_ty else '(untyped)'}")
        entries = sorted(group, key=lambda r: (r[1], r[2]))   # slug, then workspace
        total = len(entries)
        for _ty, slug, ws, desc in entries[:max_n]:
            lines.append(f"{slug} ({ws}) - {desc}")
        if total > max_n:
            lines.append(f"... {total - max_n} more (raise --max)")
    return lines


def cmd_index(args) -> int:
    max_n = parse_max(args.max)
    if args.workspace == "all":
        workspaces_root = _home() / ".cortex" / "workspaces"
        lines = _render_all(workspaces_root, max_n)
        if args.write:
            root_kdir = _home() / ".cortex" / "knowledge"
            root_kdir.mkdir(parents=True, exist_ok=True)
            out = [
                "<!-- generated by cortex kb index --workspace=all; do not edit. "
                "regenerate with: cortex kb index --workspace=all --write -->",
                "# Knowledge index (all workspaces)", "",
            ] + lines
            atomic.write_text(root_kdir / "INDEX.md", "\n".join(out) + "\n", encoding="utf-8")
            print(root_kdir / "INDEX.md")
            sync_after("index", "knowledge", "INDEX")
            return 0
        for ln in lines:
            print(ln)
        return 0
    ws_root = store.resolve_workspace(args.workspace, home=_home(), cwd=Path.cwd())
    kdir = ws_root / "knowledge"

    if args.write:
        kdir.mkdir(parents=True, exist_ok=True)
        lines = [
            "<!-- generated by cortex kb index; do not edit. regenerate with: cortex kb index --write -->",
            "# Knowledge index", "", "## knowledge",
        ]
        lines += _render_section(kdir, max_n)
        atomic.write_text(kdir / "INDEX.md", "\n".join(lines) + "\n", encoding="utf-8")
        print(kdir / "INDEX.md")
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
