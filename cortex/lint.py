"""cortex kb lint: a health check over a workspace's docs.

Karpathy's llm-wiki names lint as a first-class operation alongside ingest and
query. cortex had the other two. The gap this closes is that a knowledge base
accumulates statements that were true when written and quietly stopped being
true, and nothing noticed: this repo's README advertised `cortex viz --watch`
long after the flag was deleted, and two archived tasks described symbols in a
file that no longer existed.

The split mirrors `cortex kb ingest`. Everything a machine can decide is a
finding, printed one line per finding. Everything needing judgment goes to an
agent worklist and is phrased as a candidate, never an assertion.

Report-only unless `--fix`, which is deliberately narrow: it repairs a broken
reference ONLY when the target it names exists elsewhere under an unambiguous
address, so the edit changes an address and never a claim. It does not delete
dangling links (a link to a doc nobody has written yet is authoring intent, and
it is what the viz renders as a ghost node) and it does not touch `updated`
(bumping it would erase the very signal the stale check reads).
"""
from __future__ import annotations
import datetime
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from cortex import address
from cortex import atomic
from cortex import parser
from cortex import store
from cortex.errors import CortexError, UsageError
from cortex.kb import _home, parse_max, sync_after
from cortex.model import AUTHORED_EDGE_KINDS, Doc, World
from cortex.query import LINKABLE_KINDS
from cortex.sanitize import sanitize

CHECKS = ("broken-ref", "dead-ref", "orphan", "stale", "missing-description")
# The judgment half. Selectable by name like a check, but kept out of CHECKS
# because it produces candidates rather than findings: it never counts toward
# the tally and never decides `--strict`.
WORKLIST = "overlap"
SELECTABLE = CHECKS + (WORKLIST,)
KB_KINDS = ("knowledge", "workbench")
DEFAULT_STALE_DAYS = 180

# Boundary characters of an address token, used to bound the `--fix`
# replacement so `task-foo` never matches inside `task-foobar`.
_ADDR_CHAR = r"[A-Za-z0-9/_-]"
_FENCE = re.compile(r"^\s*```")
# The lines on which an unbracketed slug is a reference rather than a word:
# the parser's own typed body labels, and the frontmatter relation keys. Kept in
# the same order and spelling as cortex/parser.py's _BODY_REL_RE / _FM_KEY_TO_KIND.
_REL_LINE = re.compile(
    r"^\s*(?:Blocked by|Related to|Follows)\s*:|^(?:blocked_by|related_to|follows)\s*:",
    re.IGNORECASE)


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
_MAX_FILE_BYTES = 1 << 20          # 1 MiB: past this it is data, not source
_MAX_TOTAL_BYTES = 32 << 20        # 32 MiB of text read per repo, then paths only
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
            if total >= _MAX_TOTAL_BYTES:
                idx.partial = True
                continue
            try:
                size = f.stat().st_size
            except OSError:
                continue
            if f.is_symlink():
                continue                       # its target is indexed on its own
            if size > _MAX_FILE_BYTES:
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
        if _FENCE.match(line):
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


# ---- the judgment worklist ----

_STOP = frozenset("""
also from have into just like more most much only over some such than that then
this those very what when whether which while with your about after before
""".split())
_WORD = re.compile(r"[a-z0-9]{4,}")
_OVERLAP = 0.5


def _sig(text: str) -> set:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def _overlaps(docs: list) -> list:
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


# ---- --fix ----

def _replace_outside_fences(text: str, pairs) -> tuple[str, int]:
    """Rewrite each `raw` as `fix` where the text is structurally a reference.

    Two forms, and only two. Inside brackets anywhere (`[task-foo]`,
    `[[knowledge/foo]]`), and bare on a line that is a relation: a body
    `Related to:` / `Blocked by:` / `Follows:` line, or a frontmatter
    `related_to:` / `blocked_by:` / `follows:` key, which is where the parser
    reads a comma-separated list of unbracketed slugs.

    Anchoring matters. A slug is also an ordinary noun phrase, so an
    unrestricted bounded replacement rewrites prose: a doc holding both
    `[retry-policy]` and the sentence "the retry-policy changed" would come
    back saying "the knowledge/retry-policy changed". Rewriting an address is
    the contract; rewriting a sentence is not."""
    bracketed = [(re.compile(rf"\[{re.escape(raw)}\]"), fix) for raw, fix in pairs]
    bare = [(re.compile(rf"(?<!{_ADDR_CHAR}){re.escape(raw)}(?!{_ADDR_CHAR})"), fix)
            for raw, fix in pairs]
    out, in_fence, total = [], False, 0
    for line in text.split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence:
            for pat, fix in bracketed:
                line, n = pat.subn(lambda _m, f=fix: f"[{f}]", line)
                total += n
            if _REL_LINE.match(line):
                for pat, fix in bare:
                    line, n = pat.subn(lambda _m, f=fix: f, line)
                    total += n
        out.append(line)
    return "\n".join(out), total


def apply_fixes(findings: list) -> tuple[list, list]:
    """Rewrite repairable references in place. Returns (applied, files written).

    The replacement lands on the authored forms and nowhere else: bracketed
    anywhere, bare only on a relation line (see _replace_outside_fences).
    Fenced blocks are skipped for the same reason the scanner skips them: what
    is in one is an example, not a reference.

    One reference at a time, so `applied` names the references that were really
    rewritten. Grouping the whole file into a single pass would report a
    reference as fixed on the strength of a sibling's replacement -- and with
    `--strict` that turns a still-broken reference into exit 0."""
    by_path: dict = {}
    for f in findings:
        if f.check == "broken-ref" and f.fix and f.path is not None:
            by_path.setdefault(Path(f.path), []).append(f)
    applied, written = [], []
    for path, group in sorted(by_path.items()):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            raise CortexError(f"cannot read {path}: {e}")
        new = text
        done = []
        for f in group:
            new, n = _replace_outside_fences(new, [(f.raw, f.fix)])
            if n:
                done.append(f)
        if not done or new == text:
            continue
        atomic.write_text(path, new, encoding="utf-8")
        written.append(path)
        applied.extend(done)
    return applied, written


# ---- orchestration ----

def _parse_checks(raw: str) -> tuple:
    if not raw:
        return SELECTABLE
    picked = {c.strip() for c in raw.split(",") if c.strip()}
    bad = sorted(c for c in picked if c not in SELECTABLE)
    if bad:
        raise UsageError(f"--check: unknown {', '.join(bad)}; "
                         f"choose from {', '.join(SELECTABLE)}")
    return tuple(c for c in SELECTABLE if c in picked)


def _scope(args) -> tuple[Path, list]:
    """Thin adapter: unpack argparse and hand off to the shared resolver.
    `cortex query search` needs the identical (root, names) pair, so the logic
    lives in `store`, beside every other piece of workspace resolution."""
    return store.resolve_scope(args.workspace, home=_home(), cwd=Path.cwd())


def _repo_for(root: Path, ws: str, explicit: str) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_dir():
            raise CortexError(f"--repo path not found: {p}")
        return p
    recorded = store._meta_cwd(root / ws)
    if recorded:
        p = Path(recorded).expanduser()
        if p.is_dir():
            return p
    # A repo-local store is `<repo>/.cortex`, so `_scope`'s root IS the repo it
    # documents. Without this, `cortex kb lint` in a repo with a local store
    # skips dead-ref and asks for a --repo that is the directory it is standing
    # in. Guarded on the root as well as the name, since a global workspace may
    # itself be called `.cortex` and its root is not anybody's repo.
    if ws == ".cortex" and root.resolve() != (_home() / ".cortex" / "workspaces").resolve():
        return root
    return None


def collect(world: World, *, names, checks, repos, today: datetime.date,
            stale_days: int, archived: bool) -> list:
    """Every deterministic finding, in check order then doc order."""
    inbound = _inbound_authored(world) if "orphan" in checks else {}
    found: list = []
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
        if doc.id.kind == "knowledge" and "orphan" in checks and not inbound.get(canon):
            found.append(Finding("orphan", canon, "no authored backlinks"))
        if doc.id.kind in KB_KINDS:
            if "stale" in checks:
                found += _stale(doc, today, stale_days)
            if "missing-description" in checks and not (doc.description or "").strip():
                found.append(Finding("missing-description", canon, "no description: field"))
    order = {c: i for i, c in enumerate(CHECKS)}
    return sorted(found, key=lambda f: (order[f.check], f.doc, f.detail))


def _print_rows(header: str, rows: list, max_n: int) -> None:
    if not rows:
        return
    print(header)
    for r in rows[:max_n]:
        print(r)
    if len(rows) > max_n:
        print(f"... {len(rows) - max_n} more (raise --max)")
    print()


def _row(f: Finding) -> str:
    # The doc id is a store path and stays byte-exact so it can be opened; the
    # detail is doc content, which `kb ingest` may have extracted from a
    # codebase nobody here wrote, so it is sanitized before it reaches an
    # agent's terminal. Same split as ingest's worklist. See cortex/sanitize.py.
    return f"{f.doc}  ->  {sanitize(f.detail)}"


def cmd_lint(args) -> int:
    if args.repo and args.workspace == "all":
        raise UsageError("--repo cannot be combined with --workspace=all")
    selected = _parse_checks(args.check)
    checks = tuple(c for c in selected if c in CHECKS)
    max_n = parse_max(args.max)
    stale_days = parse_max(args.stale_days, "--stale-days")
    root, names = _scope(args)

    # Archives are always parsed, never always linted: a live task pointing at
    # an archived one is a resolved reference, and leaving archives out would
    # report every such link as broken. `--archive` decides what gets checked,
    # not what exists.
    world = parser.parse_world(root, include_archive=True)

    notes, repos = [], {}
    if "dead-ref" in checks:
        for ws in names:
            repo = _repo_for(root, ws, args.repo)
            if repo is None:
                notes.append(f"dead-ref skipped for {ws}: no repo "
                             f"(pass --repo, or set cwd: in the workspace .meta)")
            else:
                repos[ws] = index_repo(repo)
                if repos[ws].partial:
                    notes.append(f"dead-ref read only part of {repo.name}'s text "
                                 f"(files over {_MAX_FILE_BYTES >> 20} MiB, or past "
                                 f"{_MAX_TOTAL_BYTES >> 20} MiB total): a symbol or "
                                 f"flag living only in a skipped file reads as dead")

    findings = collect(world, names=names, checks=checks, repos=repos,
                       today=datetime.date.today(), stale_days=stale_days,
                       archived=args.archive)

    fixed, written = [], []
    if args.fix:
        fixed, written = apply_fixes(findings)
        done = {id(f) for f in fixed}
        findings = [f for f in findings if id(f) not in done]

    for check in checks:
        _print_rows(f"## {check}",
                    [_row(f) for f in findings if f.check == check], max_n)
    _print_rows("## fixed (addresses rewritten; no claim changed)",
                [_row(f) for f in fixed], max_n)

    pairs = _overlaps([world.docs[c] for c in sorted(world.docs)
                       if world.docs[c].id.kind == "knowledge"
                       and world.docs[c].id.workspace in names
                       and (args.archive or not world.docs[c].archived)]
                      ) if WORKLIST in selected else []
    if pairs:
        print("## agent worklist (needs judgment)")
        print("# Candidate pairs only. Same type and overlapping summaries is"
              " what a contradiction or a superseded claim looks like from the"
              " outside; it is also what two legitimately distinct notes look"
              " like. Read them before concluding anything.")
        for row in pairs[:max_n]:
            print(sanitize(row))
        if len(pairs) > max_n:
            print(f"... {len(pairs) - max_n} more (raise --max)")
        print()

    _print_rows("## notes", notes, max_n)

    print("## summary")
    if findings:
        tally = ", ".join(f"{c} {sum(1 for f in findings if f.check == c)}"
                          for c in checks if any(f.check == c for f in findings))
        n = len(findings)
        print(f"{n} finding{'' if n == 1 else 's'}: {tally}")
    else:
        print("no findings")
    if written:
        print(f"fixed {len(fixed)} reference{'' if len(fixed) == 1 else 's'} "
              f"in {len(written)} doc{'' if len(written) == 1 else 's'}")
        sync_after("lint", "refs", f"{len(written)} docs")

    return 1 if (args.strict and findings) else 0
