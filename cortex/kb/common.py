"""The shared base of the kb package, and of most of the engine.

`lint`, `okf`, `ingest`, `changelog` and `inject` all reach for something here.
That is why it imports nothing from cortex but `errors`: a module every other
module depends on cannot afford opinions about the store, the parser, or the
CLI.

`sync_after` is the one exception, and it imports `cortex.sync` inside the
function body deliberately, because `sync` is a consumer of this package.
"""
from __future__ import annotations
import datetime
import os
import re
from pathlib import Path

from cortex.errors import CortexError

AUTHOR_DEFAULT = "agent"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# The documented `type` vocabulary (skills/cortex-kb/SKILL.md, "type
# vocabulary"). Still a convention rather than an enum -- a custom value is
# accepted without error, and OKF §11 requires consumers to tolerate unknown
# `type` values -- so this exists only to name the canonical set in the error a
# typeless `kb new knowledge` raises.
#
# `Gotcha` sits beside `Investigation` because that is where the two overlap:
# an investigation is what you went looking for, a gotcha is what found you.
# It was missing until it was the most-used value in a real store (68 docs)
# while three of this repo's own examples already taught it, which is how a
# recommendation quietly becomes wrong. Kept in sync with the four docs that
# list it by test, not by discipline.
TYPE_VOCABULARY = ("Decision", "Design", "Reference", "Runbook",
                   "Investigation", "Gotcha", "Convention", "Comparison")

# OKF v0.2 §8 reserves lowercase `index.md` for a bundle's index. `INDEX.md` is
# what cortex derived before conformance and is retired on the next `--write`.
INDEX_NAME = "index.md"
LEGACY_INDEX_NAME = "INDEX.md"


def today() -> str:
    return datetime.date.today().isoformat()


def home_dir() -> Path:
    return Path(os.environ.get("HOME") or str(Path.home()))


def parse_max(value, flag: str = "--max") -> int:
    """Validate --max like bash did (^[0-9]+$ or die, exit 1). `flag` names the
    option in the error, so a caller reusing this for another numeric flag does
    not report a bad --stale-days as a bad --max."""
    if not re.fullmatch(r"[0-9]+", str(value)):
        raise CortexError(f"{flag} must be a non-negative integer")
    return int(value)


def sync_after(verb: str, kind: str, slug: str) -> None:
    # Best-effort: cortex.sync.push is a no-op when sync is not enabled.
    from cortex.sync import repo as sync_repo
    try:
        sync_repo.push(f"track(kb): {verb} {kind} {slug}", home=home_dir())
    except Exception:
        pass


def more_notice(total: int, max_n: int | None) -> list[str]:
    """`max_n=None` means uncapped, and an uncapped render has nothing to
    notice. `--max` bounds what a terminal prints for an agent to read; a
    derived file has no such constraint, and a catalog that silently omits
    entries is not a catalog. See `cmd_index`."""
    if max_n is None or total <= max_n:
        return []
    return [f"... {total - max_n} more (raise --max)"]


def md_escape(text: str) -> str:
    """Escape the two characters that can end a §8 entry's link text early."""
    return text.replace("[", r"\[").replace("]", r"\]")
