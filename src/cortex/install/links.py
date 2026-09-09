from __future__ import annotations

import time
from pathlib import Path

from .harnesses import (
    CURRENT_SKILL_NAMES,
    HARNESSES,
    LEGACY_SKILL_NAMES,
    install_targets,
)


def link_skill(src: Path, dest: Path) -> str:
    """Point `dest` at `src`, preserving anything real already there.

    Returns "installed", "relinked" or "replaced". A pre-existing real path is
    renamed aside rather than deleted: it may be someone's own skill.
    """
    if dest.is_symlink():
        dest.unlink()
        dest.symlink_to(src)
        return "relinked"
    if dest.exists():
        backup = dest.with_name(f"{dest.name}.bak.{int(time.time())}")
        dest.rename(backup)
        dest.symlink_to(src)
        return "replaced"
    dest.symlink_to(src)
    return "installed"


def is_owned_link(path: Path, owner_root: Path) -> bool:
    """True only for a symlink resolving inside `owner_root`.

    The uninstaller removes nothing else. A real directory, or a symlink into
    somebody else's tree, is reported rather than deleted.
    """
    if not path.is_symlink():
        return False
    try:
        target = path.resolve()
        root = owner_root.resolve()
    except OSError:
        return False
    return target == root or root in target.parents


def install_skills(*, skills_src: Path, target_root: Path,
                   home: Path) -> list[str]:
    """Symlink every skill in `skills_src` into each present harness.

    `home` is probed to decide whether a harness is in use; `target_root` is
    where links are written. The two differ only for a project-scoped install.
    """
    log: list[str] = []
    for harness in install_targets():
        harness_root = home / harness.root_rel
        if not harness_root.is_dir():
            log.append(f"[{harness.name}] {harness_root} not present, skipping")
            continue

        dest_root = target_root / harness.skills_rel
        dest_root.mkdir(parents=True, exist_ok=True)

        for legacy in LEGACY_SKILL_NAMES:
            stale = dest_root / legacy
            if stale.is_symlink():
                stale.unlink()
                log.append(f"[{harness.name}] removed stale {legacy} symlink")

        for skill_dir in sorted(d for d in skills_src.iterdir() if d.is_dir()):
            if not (skill_dir / "SKILL.md").is_file():
                log.append(
                    f"[{harness.name}] skipping {skill_dir.name} (no SKILL.md)")
                continue
            action = link_skill(skill_dir, dest_root / skill_dir.name)
            log.append(f"[{harness.name}] {action} {skill_dir.name}")
    return log


def uninstall_skills(*, target_root: Path, owner_root: Path,
                     dry_run: bool = False) -> tuple[list[str], list[str]]:
    """Remove this install's skill symlinks from every harness.

    Visits every harness in HARNESSES, not just the install targets, because a
    superseded target may still hold links from an older install. Returns
    (removed, kept); `kept` holds paths that exist but are not ours.
    """
    removed: list[str] = []
    kept: list[str] = []
    names = CURRENT_SKILL_NAMES + LEGACY_SKILL_NAMES

    for harness in HARNESSES:
        dest_root = target_root / harness.skills_rel
        if not dest_root.is_dir():
            continue
        for name in names:
            path = dest_root / name
            if not (path.exists() or path.is_symlink()):
                continue
            if is_owned_link(path, owner_root):
                if not dry_run:
                    path.unlink()
                removed.append(str(path))
            else:
                kept.append(str(path))
    return removed, kept
