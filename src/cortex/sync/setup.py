"""First-run bootstrap: clone an existing store, create a new one, or opt out.

Runs once per device. `interactive_setup` is the only prompt in the engine, and
it exists because the three choices are not inferable: whether this is the
first device or the Nth is something only the user knows.

Writing a `.sync-disabled` sentinel is a real outcome, not a no-op. It is what
stops every later checkpoint from re-asking.
"""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path

from cortex import atomic
from cortex.paths import skills_dir
from cortex.sync.repo import git, work_dir

# Resolved through cortex.paths so this does not depend on how deep the
# package sits. A stale hand-counted depth here silently skips the .gitignore
# on `setup --init`, which has happened before.
_TEMPLATE_GITIGNORE = (
    skills_dir() / "cortex-sync" / "templates" / "gitignore"
)


def _ensure_gh_authed() -> None:
    if shutil.which("gh") is None:
        raise SystemExit("setup: gh CLI not found. Install https://cli.github.com/")
    if subprocess.run(["gh", "auth", "status"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        raise SystemExit("setup: gh is not authenticated. Run: gh auth login")


def setup(mode: str, *, home, url: str | None = None, name: str = "work-tracking") -> int:
    wd = work_dir(home)
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
        shutil.rmtree(wd)
        if git(["clone", "-q", url, str(wd)], cwd=Path(home)).returncode != 0:
            raise SystemExit(f"setup: clone of {url} failed")
        print(f"cortex-sync: cloned {url} into {wd}")
        return 0

    if mode == "init":
        _ensure_gh_authed()
        if not (wd / ".git").is_dir():
            git(["init", "-q", "-b", "main"], cwd=wd)
        if _TEMPLATE_GITIGNORE.exists():
            atomic.write_text(wd / ".gitignore", _TEMPLATE_GITIGNORE.read_text())
        # Configure identity if missing (fall back to global, then a default).
        if git(["config", "user.email"], cwd=wd).returncode != 0:
            g = subprocess.run(["git", "config", "--global", "user.email"],
                               capture_output=True, text=True).stdout.strip() or "tracking@local"
            git(["config", "user.email", g], cwd=wd)
        if git(["config", "user.name"], cwd=wd).returncode != 0:
            g = subprocess.run(["git", "config", "--global", "user.name"],
                               capture_output=True, text=True).stdout.strip() or "tracking"
            git(["config", "user.name", g], cwd=wd)
        git(["add", "-A", "."], cwd=wd)
        if git(["diff", "--cached", "--quiet"], cwd=wd).returncode != 0:
            git(["commit", "-q", "-m", "track: initial sync state"], cwd=wd)
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

