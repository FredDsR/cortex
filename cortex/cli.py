"""cortex CLI: `cortex kb {new,update,index,ingest}` (+ viz/query in later phases).

Invoked as `python -m cortex.cli <group> <cmd> ...` by the cortex dispatcher.
"""
from __future__ import annotations
import argparse
import sys

from cortex import kb
from cortex import ingest
from cortex.errors import CortexError
from cortex.store import StoreError


def _add_write_flags(sp) -> None:
    sp.add_argument("kind", choices=["knowledge", "workbench"])
    sp.add_argument("slug")
    sp.add_argument("--workspace", default="")
    sp.add_argument("--session", default="")
    sp.add_argument("--author")
    sp.add_argument("--title")
    sp.add_argument("--type", dest="type")
    sp.add_argument("--description")
    sp.add_argument("--body")
    sp.add_argument("--body-from", dest="body_from")
    sp.add_argument("--open", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cortex")
    groups = p.add_subparsers(dest="group", required=True)

    kbp = groups.add_parser("kb", help="Author/query knowledge & workbench docs")
    kbcmds = kbp.add_subparsers(dest="cmd", required=True)
    _add_write_flags(kbcmds.add_parser("new"))
    _add_write_flags(kbcmds.add_parser("update"))

    idx = kbcmds.add_parser("index")
    idx.add_argument("--workspace", default="")
    idx.add_argument("--session", default="")
    idx.add_argument("--max", type=int, default=100)
    idx.add_argument("--write", action="store_true")

    ing = kbcmds.add_parser("ingest")
    ing.add_argument("--from", dest="src", default=".")
    ing.add_argument("--workspace", default="")
    ing.add_argument("--write", action="store_true")
    ing.add_argument("--only", choices=["openapi", "sql"], default=None)
    ing.add_argument("--max", type=int, default=100)
    return p


_KB_DISPATCH = {
    "new": kb.cmd_new,
    "update": kb.cmd_update,
    "index": kb.cmd_index,
    "ingest": ingest.cmd_ingest,
}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:               # argparse usage error -> exit 2
        return int(e.code) if e.code is not None else 0
    try:
        if args.group == "kb":
            return _KB_DISPATCH[args.cmd](args)
        parser.error(f"unknown group: {args.group}")
    except (CortexError, StoreError) as e:
        print(f"error: {e}", file=sys.stderr)
        return getattr(e, "code", 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
