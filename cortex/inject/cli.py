"""`cortex inject here` / `enable` / `disable` / `status`.

argparse in, terminal out. The only place this package prints.

`here` is the one command that must never fail the user: it runs at
SessionStart, so a raised exception would surface as harness noise before
anyone has typed anything. `--max` is validated before the guard, so a bad flag
still reports like every other command.
"""
from __future__ import annotations
from pathlib import Path

from cortex import atomic
from cortex import store
from cortex.inject.adapters import ADAPTERS, get_adapter
from cortex.inject.render import render_block, sentinel
from cortex.kb import common as kb_common

def cmd_here(args) -> int:
    # Validate --max up front so a bad value reports an error like every other
    # command; only the render itself is wrapped in the never-error guard.
    max_n = kb_common.parse_max(args.max)
    try:
        block = render_block(
            home=kb_common.home_dir(), cwd=Path.cwd(),
            workspace=args.workspace, session=args.session,
            max_n=max_n,
        )
    except Exception:
        return 0
    if not block:
        return 0
    if args.format == "text":
        print(block)
    else:
        print(get_adapter(args.format).format(block))
    return 0


def cmd_enable(args) -> int:
    home, cwd = kb_common.home_dir(), Path.cwd()
    wired_note = ""
    if args.wire_hook:
        get_adapter(args.wire_hook).wire(home=home)
        wired_note = f" hook wired for {args.wire_hook}."
    try:
        ws_root = store.resolve_workspace(args.workspace, home=home, cwd=cwd)
    except store.StoreError:
        if args.wire_hook:
            print(f"no workspace resolved; nothing opted in.{wired_note}")
            return 0
        raise
    atomic.write_text(sentinel(ws_root), "on\n", encoding="utf-8")
    print(f"injection enabled for workspace '{ws_root.name}'.{wired_note}")
    return 0


def cmd_disable(args) -> int:
    home, cwd = kb_common.home_dir(), Path.cwd()
    unwired_note = ""
    if args.unwire_hook:
        get_adapter(args.unwire_hook).unwire(home=home)
        unwired_note = f" hook unwired for {args.unwire_hook}."
    ws_root = store.resolve_workspace(args.workspace, home=home, cwd=cwd)
    s = sentinel(ws_root)
    if s.is_file():
        s.unlink()
    print(f"injection disabled for workspace '{ws_root.name}'.{unwired_note}")
    return 0


def cmd_status(args) -> int:
    home, cwd = kb_common.home_dir(), Path.cwd()
    ws_root = store.resolve_workspace(args.workspace, home=home, cwd=cwd)
    state = "enabled" if sentinel(ws_root).is_file() else "disabled"
    print(f"workspace '{ws_root.name}': injection {state}")
    wired = [name for name, a in sorted(ADAPTERS.items()) if a.is_wired(home=home)]
    print("wired hooks: " + (", ".join(wired) if wired else "(none)"))
    return 0
