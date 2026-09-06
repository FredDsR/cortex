"""cortex kb log: an OKF v0.2 §9 change log derived from the store's git history.

The history already exists. `cortex sync` commits after every write with a
structured subject (`track(kb): new knowledge <slug>`), so while `.git` is
present a rendered `log.md` is strictly worse than `git log --follow`, which
also gives diffs and authorship. Materialising it in the store for its own sake
would be the duplication the README criticises in a hand-maintained index.

What makes it non-redundant is export. An OKF bundle has no `.git`: a recipient
gets markdown and nothing else, and §9 `log.md` is the only portable form the
history can take. That consumer is why this exists, and it is why the renderer
never emits a link to a file the bundle would not contain.

Two things it is honest about rather than quiet about. A store is only a git
repo once somebody has run `git init` (usually via `cortex sync setup`), and
without one there is no source, so the command says so and writes nothing
rather than deriving an empty log. And a doc written but not yet committed is
invisible to git, so the header names the range actually covered instead of
implying completeness.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path

from cortex import atomic
from cortex import frontmatter as fm
from cortex import model
from cortex import store
from cortex.kb import _home, parse_max, sync_after
from cortex.sync import _git

LOG_NAME = "log.md"

# The structured subject `cortex sync` writes after a kb write. `add` is the
# bash work-kb spelling of `new`, retired at the Python port but still all over
# a real store's history (60 of 294 creations there), so dropping it would lose
# a fifth of every creation the log is supposed to record.
#
# Anchored end to end, and the slug must be a slug (same grammar as
# `kb._SLUG`), because a store also holds hand-written subjects that merely
# start the same way: `track(kb): spec in the wikilink picker` parses as verb
# `spec` under a loose pattern and is prose under this one.
_SUBJECT = re.compile(
    r"^track\(kb\): (new|add|update) knowledge ([a-z0-9][a-z0-9-]*)$")

_CREATED = ("new", "add")


def parse_subject(subject: str):
    """(verb, slug) for a knowledge write, else None.

    None covers everything that is not one: `index` commits (the tool's own
    bookkeeping, a quarter of kb commits in a real store), `lint`, workbench
    writes (session-scoped, never part of a bundle), and ordinary prose."""
    m = _SUBJECT.match(subject.strip())
    return (m.group(1), m.group(2)) if m else None


@dataclass(frozen=True)
class Entry:
    date: str          # ISO YYYY-MM-DD, the commit's author date
    verb: str          # new | add | update
    slug: str

    @property
    def created(self) -> bool:
        return self.verb in _CREATED

    @property
    def label(self) -> str:
        return "Creation" if self.created else "Update"


@dataclass
class History:
    entries: list                 # newest first
    commits: int = 0              # commits inspected, before filtering
    first: str = ""               # oldest author date seen
    last: str = ""                # newest author date seen
    uncommitted: int = 0          # knowledge files git does not yet know about


def is_git_repo(path: Path) -> bool:
    """A git dir is enough. `sync.is_enabled` additionally requires an `origin`
    remote, which is the right gate for pushing and the wrong one for reading:
    a `git init` with no remote still has every commit this reads."""
    if not path.is_dir():
        return False
    return _git(["rev-parse", "--git-dir"], cwd=path).returncode == 0


def read_history(kdir: Path, *, since: str = "") -> History:
    """Every knowledge write git knows about for KDIR, newest first.

    `--no-merges` drops sync's own merge commits declaratively rather than by
    parsing their subjects, and the pathspec keeps the read to this workspace's
    `knowledge/` so a sibling workspace's writes never appear in its log."""
    args = ["log", "--no-merges", "--date=short", "--format=%ad%x00%s"]
    if since:
        args.append(f"--since={since}")
    args += ["--", "."]
    r = _git(args, cwd=kdir, capture=True)
    if r.returncode != 0:
        return History(entries=[])

    entries, dates, commits = [], [], 0
    for line in (r.stdout or "").splitlines():
        if "\x00" not in line:
            continue
        date, subject = line.split("\x00", 1)
        commits += 1
        dates.append(date)
        parsed = parse_subject(subject)
        if parsed is not None:
            entries.append(Entry(date=date, verb=parsed[0], slug=parsed[1]))

    st = _git(["status", "--porcelain", "--", "."], cwd=kdir, capture=True)
    pending = sum(1 for ln in (st.stdout or "").splitlines()
                  if ln.strip() and not model.is_reserved(Path(ln[3:]).name))
    return History(entries=_dedupe(entries), commits=commits,
                   first=min(dates) if dates else "", last=max(dates) if dates else "",
                   uncommitted=pending)


def _dedupe(entries: list) -> list:
    """One entry per (date, slug), a creation beating an update.

    A doc touched three times in a day produced three identical commits and
    would render as three identical lines, which tells a reader nothing the
    first line did not. When a doc is both created and updated on one day, the
    creation is the event worth recording."""
    best: dict = {}
    for e in entries:
        key = (e.date, e.slug)
        prev = best.get(key)
        if prev is None or (e.created and not prev.created):
            best[key] = e
    return sorted(best.values(), key=lambda e: (e.date, e.slug), reverse=True)


def _describe(kdir: Path, slug: str) -> tuple:
    """(link text, target, description) for SLUG as it stands today, or
    (slug, "", "(no longer in the store)") when the doc is gone.

    A deleted doc still belongs in the log -- it is part of what happened -- but
    it must not be rendered as a link, because a bundle carrying a link to a
    file it does not contain is a defect in somebody else's bundle. Same rule
    #53 sets for unresolved references at the export boundary."""
    path = kdir / f"{slug}.md"
    if not path.is_file():
        return slug, "", "(no longer in the store)"
    try:
        block, _ = fm.split(path.read_text(encoding="utf-8"))
    except OSError:
        return slug, "", "(unreadable)"
    block = block or ""
    title = fm.read_field(block, "title")
    desc = model.format_description(fm.read_field(block, "description"), title)
    return (title or slug), f"{slug}.md", desc


def render(kdir: Path, hist: History, *, max_n: int | None, banner: bool) -> list[str]:
    """The §9 document: date headings newest first, each over its entries."""
    from cortex.kb import _md_escape, _more_notice

    lines: list[str] = []
    if banner:
        lines.append("<!-- generated by cortex kb log; do not edit. "
                     "regenerate with: cortex kb log --write -->")
    lines += ["# Knowledge change log", ""]
    lines += [ln for ln in _coverage(hist) if ln]
    if not hist.entries:
        lines += ["", "_No knowledge writes in the range covered._"]
        return lines

    shown = hist.entries[:max_n]
    day = ""
    for e in shown:
        if e.date != day:
            day = e.date
            lines += ["", f"## {day}", ""]
        text, target, desc = _describe(kdir, e.slug)
        body = (f"[{_md_escape(text)}]({target})" if target else _md_escape(text))
        lines.append(f"* **{e.label}**: {body} - {desc}")
    more = _more_notice(len(hist.entries), max_n)
    if more:
        lines += [""] + more
    return lines


def _coverage(hist: History) -> list[str]:
    """What the log actually covers, said plainly.

    git only knows what was committed. `sync push` runs after every write so the
    window is usually small, but with sync disabled it is unbounded, and a log
    that silently omits today's work while looking complete is worse than one
    that names its own edge."""
    if not hist.commits:
        return ["_Derived from no commits touching this directory._"]
    span = (f"{hist.first} to {hist.last}" if hist.first != hist.last else hist.first)
    out = [f"_Derived from {hist.commits} commit"
           f"{'' if hist.commits == 1 else 's'} touching `knowledge/`, {span}._"]
    if hist.uncommitted:
        out.append(f"_{hist.uncommitted} uncommitted change"
                   f"{'' if hist.uncommitted == 1 else 's'} in this directory "
                   f"are not represented._")
    return out


def cmd_log(args) -> int:
    max_n = parse_max(args.max)          # validated even when --write ignores it
    ws_root = store.resolve_workspace(args.workspace, home=_home(), cwd=Path.cwd())
    kdir = ws_root / "knowledge"

    if not is_git_repo(kdir):
        # The dead-ref pattern: a check with no source says so and reports
        # nothing, rather than reporting nothing and looking clean. Not an
        # error -- a store without `cortex sync setup` is a supported state.
        print(f"kb log: {ws_root.parent.parent if False else kdir} is not a git repo, "
              f"so there is no history to derive from "
              f"(run `cortex sync setup`, or `git init` the store)")
        return 0

    hist = read_history(kdir, since=args.since)
    if args.write:
        # Uncapped, like `kb index --write`: the file is what `cortex okf
        # export` ships, and `--since` is the knob for windowing it.
        lines = render(kdir, hist, max_n=None, banner=True)
        kdir.mkdir(parents=True, exist_ok=True)
        path = kdir / LOG_NAME
        atomic.write_text(path, "\n".join(lines) + "\n", encoding="utf-8")
        print(path)
        sync_after("log", "knowledge", LOG_NAME)
        return 0

    for ln in render(kdir, hist, max_n=max_n, banner=False):
        print(ln)
    return 0
