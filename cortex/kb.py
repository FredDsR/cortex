"""kb commands (new / update / index / ingest) for the cortex engine.

Ports skills/tracking-work-kb/bin/work-kb onto the shared core
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

from cortex import frontmatter as fm
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
        return Path(args.body_from).read_text(encoding="utf-8")
    if allow_stdin and not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def sync_after(verb: str, kind: str, slug: str) -> None:
    hook = _home() / ".claude/skills/tracking-work-sync/scripts/commit_push.sh"
    if os.access(hook, os.X_OK):
        subprocess.run(["bash", str(hook), f"track(kb): {verb} {kind} {slug}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def _maybe_open(args, path: Path) -> None:
    # bash exec's $EDITOR; we spawn+wait so an in-process caller survives.
    if args.open:
        editor = os.environ.get("EDITOR", "vi")
        subprocess.run([editor, str(path)], check=False)


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
    path.write_text(fm.emit(fields, body), encoding="utf-8")
    print(path)
    sync_after("new", args.kind, args.slug)
    _maybe_open(args, path)
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

    body = _read_body(args, allow_stdin=False) if _body_set(args) else ex_body
    fields = {"title": title, "type": typ, "author": author,
              "created": created, "updated": today(), "description": desc}
    path.write_text(fm.emit(fields, body), encoding="utf-8")
    print(path)
    sync_after("update", args.kind, args.slug)
    _maybe_open(args, path)
    return 0
