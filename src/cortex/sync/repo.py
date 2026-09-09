"""The store's git remote: plumbing, push, pull.

`kb.common.sync_after` and `viz.edit_server` both reach for `push`, so this is
the module the rest of the engine means when it says "sync". It never raises
for an ordinary git failure: `push` returns 0 even when the push fails, because
a failed push leaves the commit local and the next one will carry it.

`err` / `err_detail` live here rather than in `cli.py` because `setup.py` needs
them too, and because they write to stderr, which is diagnostics rather than
the command's output.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path


def work_dir(home) -> Path:
    return Path(home) / ".cortex"


def git(args, *, cwd, capture=False, env=None):
    return subprocess.run(
        ["git", *args], cwd=str(cwd),
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
        text=True, env=env,
    )


def err(msg: str) -> None:
    print(msg, file=sys.stderr)


def err_detail(text: str) -> None:
    """Echo captured git stderr, indented, so failures stay diagnosable."""
    text = (text or "").strip()
    if not text:
        return
    for line in text.splitlines():
        print("  " + line, file=sys.stderr)


def is_enabled(home) -> bool:
    wd = work_dir(home)
    # No store on disk -> not enabled (git -C on a missing dir would raise).
    if not wd.is_dir():
        return False
    # Sentinel wins: user explicitly opted out.
    if (wd / ".sync-disabled").exists():
        return False
    # Must be a git repo with an origin remote.
    if git(["rev-parse", "--git-dir"], cwd=wd).returncode != 0:
        return False
    if git(["remote", "get-url", "origin"], cwd=wd).returncode != 0:
        return False
    return True


def push(msg: str, *, home) -> int:
    """Stage, commit, and push the store. No-op if disabled. Idempotent when
    nothing changed. Always returns 0 (a failed push keeps the commit local)."""
    if not is_enabled(home):
        return 0
    wd = work_dir(home)

    git(["add", "-A", "."], cwd=wd)
    # Nothing staged -> done.
    if git(["diff", "--cached", "--quiet"], cwd=wd).returncode == 0:
        return 0
    git(["commit", "-q", "-m", msg], cwd=wd)

    def _push():
        return git(["push", "-q", "origin", "HEAD"], cwd=wd, capture=True)

    r = _push()
    if r.returncode == 0:
        return 0

    # Only a non-fast-forward rejection is fixable by rebasing.
    stderr = r.stderr or ""
    if not any(s in stderr.lower() for s in
               ("non-fast-forward", "fetch first", "[rejected]")):
        # Auth failure, protected branch, pre-receive hook, etc. Surface git's
        # own diagnostic so the stuck-local commit is debuggable.
        err("cortex-sync: push failed (not a fast-forward conflict); "
             "commit saved locally.")
        err_detail(stderr)
        return 0

    # Rebase onto the advanced remote, then retry once. surface mode: the
    # SUMMARY.md we just committed is a fresh edit, so a conflict on it must be
    # surfaced, not auto-resolved to upstream.
    pull_rc = pull(home=home, summary_conflict="surface")
    if pull_rc != 0:
        err(f"cortex-sync: push rejected and rebase did not complete "
             f"(rc={pull_rc}); commit saved locally.")
        return 0

    r2 = _push()
    if r2.returncode != 0:
        err("cortex-sync: push still failing; commit saved locally.")
        err_detail(r2.stderr or "")
        return 0
    return 0


def pull(*, home, summary_conflict: str = "resolve") -> int:
    """Pull --rebase the store. Auto-resolve SUMMARY.md conflicts in `resolve`
    mode; surface task/other conflicts (and SUMMARY in `surface` mode)."""
    if not is_enabled(home):
        return 0
    wd = work_dir(home)

    if git(["fetch", "-q", "origin"], cwd=wd).returncode != 0:
        err("cortex-sync: fetch failed; continuing offline")
        return 0

    if git(["pull", "-q", "--rebase", "origin", "HEAD"], cwd=wd).returncode == 0:
        return 0

    # Rebase had conflicts. Inspect them.
    conflicts = git(["diff", "--name-only", "--diff-filter=U"],
                     cwd=wd, capture=True).stdout.strip()
    if not conflicts:
        git(["rebase", "--abort"], cwd=wd)
        err("cortex-sync: pull failed (no conflicts reported)")
        return 1

    files = [f for f in conflicts.splitlines() if f]
    summary = [f for f in files if f == "SUMMARY.md" or f.endswith("/SUMMARY.md")]
    tasks_and_other = [f for f in files if f not in summary]

    must_surface = list(tasks_and_other)
    if summary_conflict == "surface":
        must_surface += summary

    if must_surface:
        git(["rebase", "--abort"], cwd=wd)
        err("cortex-sync: conflict in tracked file(s):")
        for f in files:
            err(f"  - {f}")
        err(f"Resolve manually in {wd} and re-run the skill.")
        return 2

    # Only SUMMARY.md conflicts remain -> take the upstream side (--ours during
    # rebase = the branch being rebased onto = upstream).
    for path in summary:
        git(["checkout", "--ours", "--", path], cwd=wd)
        git(["add", "--", path], cwd=wd)

    env = dict(os.environ, GIT_EDITOR="true")
    if git(["rebase", "--continue"], cwd=wd, env=env).returncode != 0:
        git(["rebase", "--abort"], cwd=wd)
        err("cortex-sync: unexpected conflict after SUMMARY auto-resolve")
        return 2

    print("cortex-sync: SUMMARY.md regenerate-needed")
    return 0


