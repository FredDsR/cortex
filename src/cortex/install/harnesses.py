from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Harness:
    """One agent harness that discovers skills from a directory.

    `install` False means uninstall still visits it but install never writes
    there. That asymmetry previously lived in a comment spanning two bash
    arrays, where nothing enforced it.
    """

    name: str
    skills_rel: str
    install: bool

    @property
    def root_rel(self) -> str:
        """The harness's own directory, e.g. ".claude" for ".claude/skills"."""
        return self.skills_rel.rsplit("/skills", 1)[0]


HARNESSES: tuple[Harness, ...] = (
    Harness("claude-code", ".claude/skills", install=True),
    Harness("codex", ".codex/skills", install=True),
    Harness("copilot-cli", ".copilot/skills", install=True),
    # Dropped as an install target in c2c399a (single-script installer +
    # Antigravity support). Kept here so older installs remain removable.
    Harness("gemini-cli", ".gemini/skills", install=False),
)


def install_targets() -> tuple[Harness, ...]:
    return tuple(h for h in HARNESSES if h.install)


# Skill directory names the installer has ever created. The uninstaller needs
# both sets, because a pre-rebrand install left tracking-work-* symlinks.
CURRENT_SKILL_NAMES: tuple[str, ...] = (
    "cortex-tracking", "cortex-github", "cortex-kb", "cortex-viz",
    "cortex-sync", "cortex-migration", "cortex-inject",
)

LEGACY_SKILL_NAMES: tuple[str, ...] = (
    "tracking-work", "tracking-work-github", "tracking-work-kb",
    "tracking-work-viz", "tracking-work-sync", "tracking-work-migration",
    "tracking-work-inject",
)
