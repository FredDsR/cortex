"""`cortex kb new` / `update` / `index`: argparse in, terminal out.

The only place this package prints, and the only place it writes an authored
doc (`index.py` writes the derived one). Slug validation, the `--type` gate and
body resolution live here because they exist to turn argparse into a decision,
and nothing outside the CLI needs them.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

from cortex import atomic
from cortex import frontmatter as fm
from cortex import model
from cortex import store
from cortex.errors import CortexError
from cortex.kb.common import (AUTHOR_DEFAULT, INDEX_NAME, SLUG,
                              TYPE_VOCABULARY, home_dir, parse_max, sync_after,
                              today)
from cortex.kb.index import render_all, render_section, write_index

def _validate_slug(slug: str, kind: str = "knowledge") -> None:
    if not SLUG.match(slug):
        raise CortexError(f"invalid slug: '{slug}' (must match [a-z0-9][a-z0-9-]*)")
    # In `knowledge/`, `index` and `log` name files cortex derives: a doc
    # authored under one is invisible everywhere (index, search, viz, lint) and
    # then overwritten the next time `kb index --write` or `kb log --write`
    # runs. Refusing up front is the only point at which the author can still be
    # told. `workbench/` has no derived files, so `log` is a fine slug there.
    if kind == "knowledge" and model.is_reserved(f"{slug}.md"):
        raise CortexError(
            f"'{slug}' is reserved in knowledge/: {slug}.md is derived by cortex "
            f"(OKF §8 index.md / §9 log.md) and would be overwritten")
def _resolve_author(args) -> str:
    if args.author is not None:
        a = args.author
    else:
        a = "human" if args.open else AUTHOR_DEFAULT
    if a not in ("human", "agent"):
        raise CortexError("author must be 'human' or 'agent'")
    return a


def _resolve_path(args, kind: str) -> Path:
    ws_root = store.resolve_workspace(args.workspace, home=home_dir(), cwd=Path.cwd())
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
    _validate_slug(args.slug, args.kind)
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
def cmd_index(args) -> int:
    # `--max` bounds the printed listing only. `--write` derives a file that
    # `cortex okf export` ships and a bundle consumer reads as the catalog, so
    # truncating it would omit docs silently and emit a `... K more` line that
    # is not an OKF §8 entry. Uncapped there, and `None` is the whole list
    # because `rows[:None]` is `rows`.
    max_n = parse_max(args.max)          # validated even when --write ignores it
    if args.write:
        max_n = None
    if args.workspace == "all":
        workspaces_root = home_dir() / ".cortex" / "workspaces"
        if args.write:
            out = [
                "<!-- generated by cortex kb index --workspace=all; do not edit. "
                "regenerate with: cortex kb index --workspace=all --write -->",
                "# Knowledge index (all workspaces)", "",
            ] + render_all(workspaces_root, max_n, okf=True)
            path = write_index(home_dir() / ".cortex" / "knowledge", out)
            print(path)
            sync_after("index", "knowledge", INDEX_NAME)
            return 0
        for ln in render_all(workspaces_root, max_n):
            print(ln)
        return 0
    ws_root = store.resolve_workspace(args.workspace, home=home_dir(), cwd=Path.cwd())
    kdir = ws_root / "knowledge"

    if args.write:
        lines = [
            "<!-- generated by cortex kb index; do not edit. regenerate with: cortex kb index --write -->",
            "# Knowledge index", "",
        ] + render_section(kdir, max_n, okf=True)
        print(write_index(kdir, lines))
        sync_after("index", "knowledge", INDEX_NAME)
        return 0

    print("## knowledge")
    for ln in render_section(kdir, max_n):
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
            for ln in render_section(wdir, max_n):
                print(ln)
    return 0


def cmd_update(args) -> int:
    _validate_slug(args.slug, args.kind)
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
