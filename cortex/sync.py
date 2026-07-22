"""cortex sync: git-backed cross-device sync of the ~/.cortex store.

A behavior-faithful port of the former tracking-work-sync bash scripts
(is_enabled / commit_push / pull / setup). Every entry point is a no-op when
sync is not enabled, so callers can invoke them unconditionally.

Exit-code / stdout contract (preserved from the bash):
  - push: always returns 0. On any push failure the commit is kept locally and a
    `cortex-sync: ...` note is printed to stderr.
  - pull: 0 on a clean rebase or an auto-resolved SUMMARY.md conflict (prints
    `cortex-sync: SUMMARY.md regenerate-needed`); 2 when a task/other conflict
    (or a SUMMARY conflict in `surface` mode) must be resolved by hand; 1 on an
    unexpected failure.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path


def _work_dir(home) -> Path:
    return Path(home) / ".cortex"


def _git(args, *, cwd, capture=False, env=None):
    return subprocess.run(
        ["git", *args], cwd=str(cwd),
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
        text=True, env=env,
    )


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _err_detail(text: str) -> None:
    """Echo captured git stderr, indented, so failures stay diagnosable."""
    text = (text or "").strip()
    if not text:
        return
    for line in text.splitlines():
        print("  " + line, file=sys.stderr)


def is_enabled(home) -> bool:
    wd = _work_dir(home)
    # No store on disk -> not enabled (git -C on a missing dir would raise).
    if not wd.is_dir():
        return False
    # Sentinel wins: user explicitly opted out.
    if (wd / ".sync-disabled").exists():
        return False
    # Must be a git repo with an origin remote.
    if _git(["rev-parse", "--git-dir"], cwd=wd).returncode != 0:
        return False
    if _git(["remote", "get-url", "origin"], cwd=wd).returncode != 0:
        return False
    return True


def push(msg: str, *, home) -> int:
    """Stage, commit, and push the store. No-op if disabled. Idempotent when
    nothing changed. Always returns 0 (a failed push keeps the commit local)."""
    if not is_enabled(home):
        return 0
    wd = _work_dir(home)

    _git(["add", "-A", "."], cwd=wd)
    # Nothing staged -> done.
    if _git(["diff", "--cached", "--quiet"], cwd=wd).returncode == 0:
        return 0
    _git(["commit", "-q", "-m", msg], cwd=wd)

    def _push():
        return _git(["push", "-q", "origin", "HEAD"], cwd=wd, capture=True)

    r = _push()
    if r.returncode == 0:
        return 0

    # Only a non-fast-forward rejection is fixable by rebasing.
    stderr = r.stderr or ""
    if not any(s in stderr.lower() for s in
               ("non-fast-forward", "fetch first", "[rejected]")):
        # Auth failure, protected branch, pre-receive hook, etc. Surface git's
        # own diagnostic so the stuck-local commit is debuggable.
        _err("cortex-sync: push failed (not a fast-forward conflict); "
             "commit saved locally.")
        _err_detail(stderr)
        return 0

    # Rebase onto the advanced remote, then retry once. surface mode: the
    # SUMMARY.md we just committed is a fresh edit, so a conflict on it must be
    # surfaced, not auto-resolved to upstream.
    pull_rc = pull(home=home, summary_conflict="surface")
    if pull_rc != 0:
        _err(f"cortex-sync: push rejected and rebase did not complete "
             f"(rc={pull_rc}); commit saved locally.")
        return 0

    r2 = _push()
    if r2.returncode != 0:
        _err("cortex-sync: push still failing; commit saved locally.")
        _err_detail(r2.stderr or "")
        return 0
    return 0


def pull(*, home, summary_conflict: str = "resolve") -> int:
    """Pull --rebase the store. Auto-resolve SUMMARY.md conflicts in `resolve`
    mode; surface task/other conflicts (and SUMMARY in `surface` mode)."""
    if not is_enabled(home):
        return 0
    wd = _work_dir(home)

    if _git(["fetch", "-q", "origin"], cwd=wd).returncode != 0:
        _err("cortex-sync: fetch failed; continuing offline")
        return 0

    if _git(["pull", "-q", "--rebase", "origin", "HEAD"], cwd=wd).returncode == 0:
        return 0

    # Rebase had conflicts. Inspect them.
    conflicts = _git(["diff", "--name-only", "--diff-filter=U"],
                     cwd=wd, capture=True).stdout.strip()
    if not conflicts:
        _git(["rebase", "--abort"], cwd=wd)
        _err("cortex-sync: pull failed (no conflicts reported)")
        return 1

    files = [f for f in conflicts.splitlines() if f]
    summary = [f for f in files if f == "SUMMARY.md" or f.endswith("/SUMMARY.md")]
    tasks_and_other = [f for f in files if f not in summary]

    must_surface = list(tasks_and_other)
    if summary_conflict == "surface":
        must_surface += summary

    if must_surface:
        _git(["rebase", "--abort"], cwd=wd)
        _err("cortex-sync: conflict in tracked file(s):")
        for f in files:
            _err(f"  - {f}")
        _err(f"Resolve manually in {wd} and re-run the skill.")
        return 2

    # Only SUMMARY.md conflicts remain -> take the upstream side (--ours during
    # rebase = the branch being rebased onto = upstream).
    for path in summary:
        _git(["checkout", "--ours", "--", path], cwd=wd)
        _git(["add", "--", path], cwd=wd)

    env = dict(os.environ, GIT_EDITOR="true")
    if _git(["rebase", "--continue"], cwd=wd, env=env).returncode != 0:
        _git(["rebase", "--abort"], cwd=wd)
        _err("cortex-sync: unexpected conflict after SUMMARY auto-resolve")
        return 2

    print("cortex-sync: SUMMARY.md regenerate-needed")
    return 0


# --- setup -----------------------------------------------------------------

_TEMPLATE_GITIGNORE = (
    Path(__file__).resolve().parent.parent
    / "skills" / "cortex-sync" / "templates" / "gitignore"
)


def _ensure_gh_authed() -> None:
    import shutil
    if shutil.which("gh") is None:
        raise SystemExit("setup: gh CLI not found. Install https://cli.github.com/")
    if subprocess.run(["gh", "auth", "status"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        raise SystemExit("setup: gh is not authenticated. Run: gh auth login")


def setup(mode: str, *, home, url: str | None = None, name: str = "work-tracking") -> int:
    wd = _work_dir(home)
    wd.mkdir(parents=True, exist_ok=True)

    if mode == "skip":
        (wd / ".sync-disabled").touch()
        print(f"cortex-sync: disabled (sentinel written at {wd / '.sync-disabled'})")
        return 0

    if mode == "clone":
        if url is None:
            raise SystemExit("setup: --clone requires a URL")
        # Refuse if the store has content other than the sentinel.
        for child in wd.iterdir():
            if child.name != ".sync-disabled":
                raise SystemExit(
                    f"setup: {wd} is not empty; refusing to clone over existing content.")
        _ensure_gh_authed()
        import shutil
        shutil.rmtree(wd)
        if _git(["clone", "-q", url, str(wd)], cwd=Path(home)).returncode != 0:
            raise SystemExit(f"setup: clone of {url} failed")
        print(f"cortex-sync: cloned {url} into {wd}")
        return 0

    if mode == "init":
        _ensure_gh_authed()
        if not (wd / ".git").is_dir():
            _git(["init", "-q", "-b", "main"], cwd=wd)
        if _TEMPLATE_GITIGNORE.exists():
            (wd / ".gitignore").write_text(_TEMPLATE_GITIGNORE.read_text())
        # Configure identity if missing (fall back to global, then a default).
        if _git(["config", "user.email"], cwd=wd).returncode != 0:
            g = subprocess.run(["git", "config", "--global", "user.email"],
                               capture_output=True, text=True).stdout.strip() or "tracking@local"
            _git(["config", "user.email", g], cwd=wd)
        if _git(["config", "user.name"], cwd=wd).returncode != 0:
            g = subprocess.run(["git", "config", "--global", "user.name"],
                               capture_output=True, text=True).stdout.strip() or "tracking"
            _git(["config", "user.name", g], cwd=wd)
        _git(["add", "-A", "."], cwd=wd)
        if _git(["diff", "--cached", "--quiet"], cwd=wd).returncode != 0:
            _git(["commit", "-q", "-m", "track: initial sync state"], cwd=wd)
        if subprocess.run(["gh", "repo", "create", name, "--private",
                           "--source", str(wd), "--push"]).returncode != 0:
            raise SystemExit(f"setup: gh repo create '{name}' failed")
        print(f"cortex-sync: initialized repo '{name}' and pushed from {wd}")
        return 0

    raise SystemExit(f"setup: unknown mode '{mode}'")


def interactive_setup(home) -> int:
    """No-flag `cortex sync setup`: prompt clone / create / skip, matching the
    former setup.sh menu (including <owner>/<repo> shorthand normalization)."""
    print("cortex-sync setup")
    print("-----------------")
    print("1) Clone an existing sync repo (for a second/Nth device)")
    print("2) Create a new sync repo (first device)")
    print("3) Skip (local only)")
    print()
    try:
        choice = input("Choose [1/2/3]: ").strip()
        if choice == "1":
            url = input("Clone URL or <owner>/<repo>: ").strip()
            if "://" not in url and "@" not in url:
                url = f"https://github.com/{url}.git"
            return setup("clone", home=home, url=url)
        if choice == "2":
            name = input("Repo name [work-tracking]: ").strip() or "work-tracking"
            return setup("init", home=home, name=name)
        if choice == "3":
            return setup("skip", home=home)
    except EOFError:
        raise SystemExit("setup: no input on stdin; "
                         "pass --skip / --clone URL / --init [--name N] explicitly")
    raise SystemExit("setup: unknown choice (expected 1/2/3)")


# --- CLI wrappers ----------------------------------------------------------

def cmd_push(args) -> int:
    return push(args.message, home=Path.home())


def cmd_pull(args) -> int:
    return pull(home=Path.home(),
                summary_conflict=getattr(args, "summary_conflict", "resolve"))


def cmd_status(args) -> int:
    home = Path.home()
    if is_enabled(home):
        wd = _work_dir(home)
        remote = _git(["remote", "get-url", "origin"], cwd=wd, capture=True).stdout.strip()
        print(f"cortex-sync: enabled (origin: {remote})")
        return 0
    print("cortex-sync: not enabled")
    return 1


def cmd_setup(args) -> int:
    if getattr(args, "skip", False):
        return setup("skip", home=Path.home())
    if getattr(args, "clone", None):
        return setup("clone", home=Path.home(), url=args.clone)
    if getattr(args, "init", False):
        return setup("init", home=Path.home(), name=getattr(args, "name", None) or "work-tracking")
    # No flags: fall back to the interactive menu (matches the docs).
    return interactive_setup(Path.home())
