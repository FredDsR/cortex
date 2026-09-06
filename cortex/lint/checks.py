"""The deterministic half of `cortex kb lint`: a `World` in, findings out.

Every check here is a pure function of the docs it is handed, so adding a sixth
one is a function plus a name in `CHECKS` plus a branch in `collect`, all in
this file. The three names without a leading underscore that look like
internals (`FENCE`, `MAX_*_BYTES`, `OKF_ENTRY`) are public because they cross a
module boundary: `fix.py` skips the same fenced blocks the scanner does,
`cli.py` prints the budgets in the note that says the corpus had holes, and
`okf.bundle` validates an exported index against the same §8 entry grammar this
check reads a derived one with -- one definition, so a bundle cortex writes and
a bundle cortex lints can only ever agree.
"""
from __future__ import annotations
import datetime
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from cortex import address
from cortex import kb
from cortex import parser
from cortex.model import AUTHORED_EDGE_KINDS, Doc, World
from cortex.query import LINKABLE_KINDS

CHECKS = ("broken-ref", "dead-ref", "orphan", "stale", "missing-description", "okf")
# The judgment half. Selectable by name like a check, but kept out of CHECKS
# because it produces candidates rather than findings: it never counts toward
# the tally and never decides `--strict`.
WORKLIST = "overlap"
SELECTABLE = CHECKS + (WORKLIST,)
KB_KINDS = ("knowledge", "workbench")
DEFAULT_STALE_DAYS = 180

# A fenced block delimiter. Shared with `fix.py`, which skips fences for the
# same reason the scanner does: what is inside one is an example, not a
# reference.
FENCE = re.compile(r"^\s*```")


@dataclass(frozen=True)
class Finding:
    check: str
    doc: str                       # canonical doc id, printed verbatim
    detail: str                    # free text, sanitized before printing
    raw: str = ""                  # the raw reference text, for --fix
    fix: str = ""                  # its repaired address, "" when unrepairable
    path: Path | None = None       # the file --fix would rewrite


# ---- repo index (for dead-ref) ----

# Directories that hold either generated output or somebody else's code. A
# vendored dependency is pruned because a doc naming one of its symbols is not
# what this check is about, and walking it is most of the cost.
_PRUNE = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
          ".mypy_cache", ".pytest_cache", ".ruff_cache", ".worktrees", ".cortex",
          "dist", "build", "target", "vendor", ".next", ".tox", "coverage"}
MAX_FILE_BYTES = 1 << 20          # 1 MiB: past this it is data, not source
MAX_TOTAL_BYTES = 32 << 20        # 32 MiB of text read per repo, then paths only
_TOKEN = re.compile(r"--[A-Za-z0-9][A-Za-z0-9-]*|[A-Za-z_][A-Za-z0-9_]*")


@dataclass
class RepoIndex:
    """Everything the dead-ref check asks of a repo: which relative paths and
    basenames exist, and which identifiers and long flags appear anywhere in its
    text. Membership is the only question asked, so an over-broad corpus (a
    binary decoded with errors="replace", a generated file) can only suppress a
    finding, never invent one. Erring toward silence is the right direction for
    a check whose false positives each cost a human a look. The one gap in that
    argument is a corpus with holes -- see `partial`."""
    root: Path
    paths: set = field(default_factory=set)
    basenames: set = field(default_factory=set)
    tokens: set = field(default_factory=set)
    # True when some file's text was not read (too large, or past the total
    # budget). Membership then has a hole, and a hole in `tokens` is the
    # one way this index can invent a finding: a symbol that lives only in a
    # skipped file reads as dead. Surfaced as a note so the reader knows the
    # symbol and flag rows are not authoritative for this repo.
    partial: bool = False

    def has_path(self, rel: str) -> bool:
        # `.exists()` as the fallback so a path under a pruned directory
        # (node_modules/..., dist/...) is found rather than reported dead.
        if rel in self.paths or rel in self.basenames:
            return True
        try:
            return (self.root / rel).exists()
        except OSError:
            return False

    def has_token(self, name: str) -> bool:
        return name in self.tokens


def index_repo(repo: Path) -> RepoIndex:
    idx = RepoIndex(root=repo)
    total = 0
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = sorted(d for d in dirnames if d not in _PRUNE)
        here = Path(dirpath)
        for d in dirnames:
            idx.paths.add((here / d).relative_to(repo).as_posix())
        for fn in filenames:
            f = here / fn
            idx.paths.add(f.relative_to(repo).as_posix())
            idx.basenames.add(fn)
            if total >= MAX_TOTAL_BYTES:
                idx.partial = True
                continue
            try:
                size = f.stat().st_size
            except OSError:
                continue
            if f.is_symlink():
                continue                       # its target is indexed on its own
            if size > MAX_FILE_BYTES:
                idx.partial = True
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            total += size
            idx.tokens.update(_TOKEN.findall(text))
    return idx


# ---- candidate code references in a doc body ----

_CODE_SPAN = re.compile(r"`([^`\n]+)`")
_LINE_SUFFIX = re.compile(r":\d+(?:-\d+)?$")
_FLAG = re.compile(r"^--[a-z][a-z0-9-]*$")
_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\(\))?$")
# A word only counts as a symbol when it is shaped like code rather than like a
# noun: an underscore, an internal capital, or a call suffix. Without this gate
# every backticked English word in the store becomes a lookup, and the check
# drowns in findings about prose.
_CODEISH = re.compile(r"_|\(\)|[a-z][A-Z]")
_NOT_A_NAME = re.compile(r"[<>\[\]{}|*?=]")

# A dotted word is only a filename when its last segment is a file extension.
# Without the allowlist, `args.max` and `doc.rel_path` read as paths and every
# doc that names an attribute produces a finding. Erring toward silence: an
# extension missing from this set costs one unreported dead path, while a
# missing gate costs a finding on ordinary prose about code.
_FILE_EXT = frozenset("""
bash bat c cc cfg cjs cmd conf cpp cs css csv dockerfile env fish gif gitignore
go gradle h hpp htm html ini ipynb java jpeg jpg js json jsx kt kts less lock
lua m makefile markdown md mjs mk mm pl plist png proto ps1 php py pyi rb rs
rst sass sbt scss sh sql svg swift tf tfvars toml ts tsv tsx txt xml yaml yml
zsh
""".split())


def _code_words(body: str):
    """Yield candidate code references from BODY's inline code spans.

    Only inline spans, and only outside fenced blocks. Both restrictions are
    about precision: a backtick is the author saying "this is code", and a
    fenced block is usually an illustration whose identifiers were never
    claimed to exist."""
    in_fence = False
    for line in body.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for span in _CODE_SPAN.findall(line):
            for word in span.split():
                word = word.strip(" \t,;:.()[]{}<>\"'|")
                if word:
                    yield word


def _classify(word: str) -> tuple[str, str] | None:
    """(kind, needle) for a candidate, or None when it is not checkable.

    `dir-path` is a slash-bearing word with no file extension. It is only
    checkable if the repo already knows its leading segment as a directory, so
    the decision needs the index and is deferred to _dead_refs -- otherwise a
    backticked `and/or` becomes a missing path."""
    if "://" in word or word.startswith("#") or len(word) < 3:
        return None
    if word.startswith("--"):
        head = word.split("=", 1)[0]                     # --workspace=all -> --workspace
        return ("flag", head) if _FLAG.match(head) else None
    # A placeholder (`knowledge/<slug>.md`), a glob, an assignment, or a
    # markdown remnant (`label](path.md`) is not a name the repo was ever
    # supposed to hold.
    if _NOT_A_NAME.search(word):
        return None
    # `~/.claude/settings.json`, `$HOME/x`: resolved against something other
    # than the repo, so the repo not having it says nothing.
    if word[0] in "~$":
        return None
    bare = _LINE_SUFFIX.sub("", word.split("#", 1)[0])   # ingest.py:357#x -> ingest.py
    if not bare or bare.startswith("/") or ".." in bare:
        return None                            # absolute or traversing: not ours
    ext = bare.rsplit(".", 1)[-1].lower() if "." in bare else ""
    if ext in _FILE_EXT:
        return ("path", bare)
    if "/" in bare:
        return ("dir-path", bare.rstrip("/"))
    if "." in bare:
        return None                            # attribute access, not a filename
    if _SYMBOL.match(bare) and _CODEISH.search(bare):
        return ("symbol", bare.removesuffix("()"))
    return None


def _dead_refs(doc: Doc, idx: RepoIndex) -> list:
    out, seen = [], set()
    for word in _code_words(doc.body):
        c = _classify(word)
        if c is None:
            continue
        kind, needle = c
        if needle in seen:
            continue
        seen.add(needle)
        if kind == "dir-path":
            if needle.split("/", 1)[0] not in idx.paths:
                continue                       # not a path this repo ever had
            kind = "path"
        live = idx.has_path(needle) if kind == "path" else idx.has_token(needle)
        if not live:
            out.append(Finding("dead-ref", doc.id.canonical(),
                               f"{needle} ({kind} not in {idx.root.name})"))
    return out


# ---- broken references ----

def _repair(world: World, doc: Doc, raw_target: str) -> str:
    """The address a broken reference should have had, or "".

    A reference is repairable only when the slug it names belongs to exactly one
    doc in the world. That is the whole safety argument: the author meant a doc
    that exists, only the address was wrong, so rewriting it changes no claim. A
    slug nothing in the store answers to is left alone -- it is either a typo
    lint cannot resolve or a deliberate placeholder for a doc not yet written."""
    token = raw_target.strip().strip("[]").strip()
    parts = [p for p in token.split("/") if p]
    if not parts:
        return ""
    slug = parts[-1]
    want = "knowledge" if "knowledge" in parts else (
        "workbench" if "workbench" in parts else "")

    def _pick(kinds) -> list:
        return [d for d in world.docs.values()
                if d.id.kind in kinds and d.id.slug == slug
                and d.id.canonical() != doc.id.canonical()]

    # An unqualified token resolves to a task by the address grammar, so a task
    # match is the intended reading; a kb doc is the fallback reading.
    cands = _pick((want,)) if want else (_pick(("task",)) or _pick(LINKABLE_KINDS))
    if len(cands) != 1:
        return ""
    fixed = address.abbreviate(cands[0].id, doc.id)
    return "" if fixed == token else fixed


def _broken_refs(world: World, doc: Doc) -> list:
    out, seen = [], set()
    for raw in parser.raw_refs(doc):
        res = address.resolve(raw.raw_target, referencing=doc.id)
        if res.resolved and res.doc_id.canonical() in world.docs:
            continue
        if raw.raw_target in seen:
            continue
        seen.add(raw.raw_target)
        fixed = _repair(world, doc, raw.raw_target)
        detail = (f"{raw.raw_target} -> {fixed} (repairable)" if fixed
                  else f"{raw.raw_target} (no such doc)")
        out.append(Finding("broken-ref", doc.id.canonical(), detail,
                           raw=raw.raw_target, fix=fixed, path=doc.rel_path))
    return out


# ---- the remaining checks ----

def _inbound_authored(world: World) -> dict:
    """canonical id -> count of inbound edges an author wrote (`contains` is
    structural, so it does not rescue a doc from being an orphan)."""
    counts: dict = {}
    for e in world.edges:
        if e.kind not in AUTHORED_EDGE_KINDS:
            continue
        s, t = e.source.canonical(), e.target.canonical()
        if s == t:
            continue
        counts[t] = counts.get(t, 0) + 1
    return counts


def _stale(doc: Doc, today: datetime.date, days: int) -> list:
    raw = (doc.updated or "").strip()
    if not raw:
        return [Finding("stale", doc.id.canonical(), "no updated: field")]
    try:
        when = datetime.date.fromisoformat(raw)
    except ValueError:
        return [Finding("stale", doc.id.canonical(), f"unparseable updated: {raw}")]
    age = (today - when).days
    if age > days:
        return [Finding("stale", doc.id.canonical(), f"updated {raw} ({age}d > {days}d)")]
    return []


# ---- OKF v0.2 §11 conformance ----

# A §8 index entry: `* [Title](relative-url) - description`. Everything else a
# derived index holds (the banner comment, headings, the `... K more` notice,
# blank lines) is not an entry and is not checked against this.
#
# The link text is `.+` and greedy rather than `[^\]]+`: a title carrying a
# bracket (escaped by `kb._md_escape`, or literal in an index derived before
# that) still ends its link at the last `](`, and reading such a line as a hand
# edit would flag a freshly derived index that nothing can fix.
OKF_ENTRY = re.compile(r"^\* \[.+\]\([^)]+\)")


def _okf_doc(doc: Doc) -> list:
    """§11 asks three things of a bundle. The first cortex cannot violate: a
    file without frontmatter never becomes a `Doc` in the first place. The
    third is the index, checked per-directory in `_okf_index`. This is the
    second: a non-empty `type`.

    The finding doubles as the backfill worklist for a store written before the
    rule, which is why it carries the title and description: an agent needs
    both to choose a value, and a migration that guesses one would make the
    store conformant and the field meaningless."""
    if (doc.type or "").strip():
        return []
    return [Finding("okf", doc.id.canonical(),
                    f"no type: field (OKF §11) - {doc.title or '(no title)'} - "
                    f"{doc.description or '(no description)'}")]


def _okf_index(kdir: Path, label: str) -> list:
    """The §8 half, which is per-directory rather than per-doc: a legacy
    `INDEX.md` left over from before the rename, and an `index.md` carrying
    lines that are not §8 entries (which is what a hand edit looks like, and
    the banner says not to make one).

    `label` names the directory in the id column. The caller supplies it rather
    than this deriving it from a workspace name, because the root brain index
    belongs to no workspace and would otherwise be unreachable."""
    # A directory rather than a doc, so the id column names it as one. It is
    # still a store path, which is what the column promises: openable as typed.
    out, doc = [], f"{label}/knowledge/"
    legacy, current = kdir / kb.LEGACY_INDEX_NAME, kdir / kb.INDEX_NAME
    if legacy.exists() and not (current.exists() and legacy.samefile(current)):
        out.append(Finding("okf", doc, f"{kb.LEGACY_INDEX_NAME} alongside the "
                                       f"index (§8 reserves lowercase "
                                       f"{kb.INDEX_NAME}); regenerate with "
                                       f"cortex kb index --write"))
    if not current.is_file():
        return out
    try:
        text = current.read_text(encoding="utf-8")
    except OSError:
        return out
    for n, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        if (not stripped or stripped.startswith(("#", "<!--", "..."))
                or OKF_ENTRY.match(stripped)):
            continue
        out.append(Finding("okf", doc, f"{kb.INDEX_NAME}:{n} is not a §8 entry "
                                       f"(`* [Title](url) - description`); "
                                       f"regenerate with cortex kb index --write"))
        break                          # one finding per index; the fix is the same
    return out


# ---- the judgment worklist ----

_STOP = frozenset("""
also from have into just like more most much only over some such than that then
this those very what when whether which while with your about after before
""".split())
_WORD = re.compile(r"[a-z0-9]{4,}")
_OVERLAP = 0.5


def _sig(text: str) -> set:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def overlaps(docs: list) -> list:
    """Candidate pairs for the contradiction / superseded reading. Same type,
    and titles-plus-descriptions that overlap past a threshold.

    Reported as a worklist, not a finding, and that is the point: this is the
    shape of check that would be wrong as an assertion (a store can deliberately
    hold both `auth-tokens` and `token-refresh`) but is useful as a short list
    somebody looks at."""
    rows = []
    prepped = [(d, _sig(f"{d.title or ''} {d.description or ''}")) for d in docs]
    for i, (a, sa) in enumerate(prepped):
        if len(sa) < 2:
            continue
        for b, sb in prepped[i + 1:]:
            if (a.type or "").lower() != (b.type or "").lower() or len(sb) < 2:
                continue
            shared = sa & sb
            if len(shared) < 2 or len(shared) / len(sa | sb) < _OVERLAP:
                continue
            rows.append(f"{a.id.canonical()}  ~  {b.id.canonical()}  "
                        f"(shared: {', '.join(sorted(shared))})")
    return sorted(rows)


# ---- the run ----

def collect(world: World, *, names, checks, repos, today: datetime.date,
            stale_days: int, archived: bool, index_dirs=()) -> list:
    """Every deterministic finding, in check order then doc order.

    `index_dirs` is `(directory, label)` per derived index the run covers. Only
    the §8 half of `okf` reads it, because a derived index is a file the world
    never parses into a `Doc`. The caller builds the list, since which indexes a
    run covers is a scope question and scope lives in `cmd_lint`."""
    inbound = _inbound_authored(world) if "orphan" in checks else {}
    found: list = []
    if "okf" in checks:
        for kdir, label in index_dirs:
            found += _okf_index(kdir, label)
    for canon in sorted(world.docs):
        doc = world.docs[canon]
        if doc.id.kind not in LINKABLE_KINDS or doc.id.workspace not in names:
            continue
        if doc.archived and not archived:
            continue
        if "broken-ref" in checks:
            found += _broken_refs(world, doc)
        if "dead-ref" in checks:
            idx = repos.get(doc.id.workspace)
            if idx is not None:
                found += _dead_refs(doc, idx)
        if doc.id.kind == "knowledge":
            if "orphan" in checks and not inbound.get(canon):
                found.append(Finding("orphan", canon, "no authored backlinks"))
            if "okf" in checks:
                # knowledge/ only: workbench is session-scoped and never
                # exported, so §11 does not reach it. Same exemption as
                # `kb new`. See cortex.kb._require_type.
                found += _okf_doc(doc)
        if doc.id.kind in KB_KINDS:
            if "stale" in checks:
                found += _stale(doc, today, stale_days)
            if "missing-description" in checks and not (doc.description or "").strip():
                found.append(Finding("missing-description", canon, "no description: field"))
    order = {c: i for i, c in enumerate(CHECKS)}
    return sorted(found, key=lambda f: (order[f.check], f.doc, f.detail))
