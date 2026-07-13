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
    idx.add_argument("--max", default="100")          # validated in cmd (exit 1, bash parity)
    idx.add_argument("--write", action="store_true")

    ing = kbcmds.add_parser("ingest")
    ing.add_argument("--from", dest="src", default=".")
    ing.add_argument("--workspace", default="")
    ing.add_argument("--write", action="store_true")
    ing.add_argument("--only", default="")            # "" = no filter; validated in cmd
    ing.add_argument("--max", default="100")

    # viz owns its own parser in cortex.viz.cli (build/serve + their flags).
    # Registered here only so `cortex --help` and invalid-group errors list it;
    # main() intercepts the `viz` group before argparse and forwards the rest to
    # viz_main verbatim (argparse REMAINDER can't reliably carry a leading option
    # like `--help`, so delegation, not parsing, is how viz args are handled).
    vp = groups.add_parser("viz", add_help=False,
                           help="Visualize the work tree (build, serve)")
    vp.add_argument("args", nargs=argparse.REMAINDER)
    return p


# Value-taking flags whose argument may legitimately start with "-" (e.g. a
# description like "-> notes"). argparse rejects `--flag -x` in space form, so we
# rewrite `--flag value` -> `--flag=value` (the "=" form accepts leading dashes),
# matching the bash parser which stored $2 verbatim.
_VALUE_FLAGS = {"--workspace", "--session", "--author", "--title", "--type",
                "--description", "--body", "--body-from", "--from", "--only", "--max"}


def _glue_flag_values(argv):
    out, i, n = [], 0, len(argv)
    while i < n:
        a = argv[i]
        if a in _VALUE_FLAGS and i + 1 < n:
            out.append(f"{a}={argv[i + 1]}")
            i += 2
        else:
            out.append(a)
            i += 1
    return out


_KB_DISPATCH = {
    "new": kb.cmd_new,
    "update": kb.cmd_update,
    "index": kb.cmd_index,
    "ingest": ingest.cmd_ingest,
}


def _exit_code(e: SystemExit) -> int:
    """Normalize a SystemExit to a process exit code, mirroring CPython: None -> 0,
    an int passes through, anything else prints to stderr and yields 1. Keeps
    main() uniformly int-returning even if a delegate raises SystemExit("msg")."""
    if e.code is None:
        return 0
    if isinstance(e.code, int):
        return e.code
    print(e.code, file=sys.stderr)
    return 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "viz":
        # Delegate to viz's own parser (keeps its flags + `cortex viz` help verbatim).
        from cortex.viz.cli import main as viz_main
        try:
            return viz_main(argv[1:])
        except SystemExit as e:
            return _exit_code(e)
    parser = build_parser()
    try:
        args = parser.parse_args(_glue_flag_values(argv))
    except SystemExit as e:               # argparse usage error -> exit 2
        return _exit_code(e)
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
