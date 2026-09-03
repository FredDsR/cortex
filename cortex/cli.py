"""cortex CLI: `cortex kb {new,update,index,ingest,lint}` (+ viz/query/inject/sync).

Invoked as `python -m cortex.cli <group> <cmd> ...` by the cortex dispatcher.
"""
from __future__ import annotations
import argparse
import sys

from cortex import kb
from cortex import ingest
from cortex import lint
from cortex import query
from cortex import search as search_mod
from cortex import inject
from cortex import migrate_store
from cortex import sync
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

    lp = kbcmds.add_parser("lint")
    lp.add_argument("--workspace", default="")        # "all" lints every workspace
    lp.add_argument("--repo", default="")             # dead-ref target; default: .meta cwd
    lp.add_argument("--check", default="")            # comma list; "" = every check
    lp.add_argument("--stale-days", dest="stale_days", default=str(lint.DEFAULT_STALE_DAYS))
    lp.add_argument("--max", default="50")
    lp.add_argument("--archive", action="store_true")
    lp.add_argument("--fix", action="store_true")
    lp.add_argument("--strict", action="store_true")  # exit 1 when findings remain

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

    qp = groups.add_parser("query", help="Query the work graph (neighbors, search)")
    qcmds = qp.add_subparsers(dest="cmd", required=True)
    nb = qcmds.add_parser("neighbors",
                          help="Show a doc's links, backlinks, and ghost refs")
    nb.add_argument("slug")
    nb.add_argument("--workspace", default="")
    nb.add_argument("--session", default="")
    nb.add_argument("--kind", choices=["task", "knowledge", "workbench"], default="")
    nb.add_argument("--max", default="20")

    se = qcmds.add_parser("search",
                          help="BM25 keyword search over knowledge and tasks")
    se.add_argument("terms", nargs="+")
    se.add_argument("--workspace", default="")     # "all" searches every workspace
    se.add_argument("--kind",
                    choices=["knowledge", "workbench", "task", "all"],
                    default="all")
    se.add_argument("--max", default="10")
    se.add_argument("--archive", action="store_true")

    ip = groups.add_parser("inject", help="Opt-in session-start injection")
    icmds = ip.add_subparsers(dest="cmd", required=True)

    here = icmds.add_parser("here", help="Render the injection block for this context")
    here.add_argument("--format", choices=["text", "claude-code"], default="text")
    here.add_argument("--workspace", default="")
    here.add_argument("--session", default="")
    here.add_argument("--max", default="100")

    en = icmds.add_parser("enable", help="Opt this workspace in (+ optional --wire-hook)")
    en.add_argument("--workspace", default="")
    en.add_argument("--wire-hook", default="")

    dis = icmds.add_parser("disable", help="Opt this workspace out (+ optional --unwire-hook)")
    dis.add_argument("--workspace", default="")
    dis.add_argument("--unwire-hook", default="")

    st = icmds.add_parser("status", help="Show sentinel state + wired harnesses")
    st.add_argument("--workspace", default="")

    msp = groups.add_parser("migrate-store",
                            help="Move the store from ~/.work to ~/.cortex (dry-run default)")
    msp.add_argument("--write", action="store_true")

    syp = groups.add_parser("sync", help="Sync the ~/.cortex store to a private GitHub repo")
    scmds = syp.add_subparsers(dest="cmd", required=True)
    pushp = scmds.add_parser("push", help="Stage, commit, and push the store")
    pushp.add_argument("message")
    pullp = scmds.add_parser("pull", help="Pull --rebase the store")
    pullp.add_argument("--summary-conflict", dest="summary_conflict",
                       choices=["resolve", "surface"], default="resolve")
    setupp = scmds.add_parser("setup", help="Bootstrap sync (skip / clone / init)")
    setupp.add_argument("--skip", action="store_true")
    setupp.add_argument("--clone", default="")
    setupp.add_argument("--init", action="store_true")
    setupp.add_argument("--name", default="")
    scmds.add_parser("status", help="Show sync state (enabled + origin)")
    return p


# Value-taking flags whose argument may legitimately start with "-" (e.g. a
# description like "-> notes"). argparse rejects `--flag -x` in space form, so we
# rewrite `--flag value` -> `--flag=value` (the "=" form accepts leading dashes),
# matching the bash parser which stored $2 verbatim.
_VALUE_FLAGS = {"--workspace", "--session", "--author", "--title", "--type",
                "--description", "--body", "--body-from", "--from", "--only", "--max",
                "--format", "--wire-hook", "--unwire-hook", "--repo", "--check",
                "--stale-days", "--kind"}


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
    "lint": lint.cmd_lint,
}

_QUERY_DISPATCH = {
    "neighbors": query.cmd_neighbors,
    "search": search_mod.cmd_search,
}

_INJECT_DISPATCH = {
    "here": inject.cmd_here,
    "enable": inject.cmd_enable,
    "disable": inject.cmd_disable,
    "status": inject.cmd_status,
}

_SYNC_DISPATCH = {
    "push": sync.cmd_push,
    "pull": sync.cmd_pull,
    "setup": sync.cmd_setup,
    "status": sync.cmd_status,
}

_GROUP_DISPATCH = {
    "kb": _KB_DISPATCH,
    "query": _QUERY_DISPATCH,
    "inject": _INJECT_DISPATCH,
    "sync": _SYNC_DISPATCH,
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
    if args.group == "migrate-store":
        return migrate_store.cmd_migrate_store(args)
    try:
        dispatch = _GROUP_DISPATCH.get(args.group)
        if dispatch is not None:
            return dispatch[args.cmd](args)
        parser.error(f"unknown group: {args.group}")
    except (CortexError, StoreError) as e:
        print(f"error: {e}", file=sys.stderr)
        return getattr(e, "code", 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
