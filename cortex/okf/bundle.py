"""Reading and writing an OKF v0.2 bundle: the two IO passes behind `cortex okf`.

A bundle is a directory of markdown concepts plus the two reserved files §8 and
§9 name (`index.md`, `log.md`). Everything here is store-shaped on one side and
bundle-shaped on the other; the translation between the two link grammars lives
in `links`, and nothing here prints.

**Import is an untrusted input path.** A bundle was written by somebody else,
and its `description:` fields land in the `<cortex-index>` block `cortex inject`
hands a fresh agent at SessionStart, before the user has said anything. That is
the same exposure #35 closed on the ingest path. So every string read out of a
bundle goes through `cortex.sanitize` -- not the ones that look risky, all of
them, including the body. The rule `sanitize.py` states for the store (a
person's own notes are never rewritten) is what makes this the other side of
the same coin: a foreign bundle is not the person's own notes.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from cortex import atomic
from cortex import changelog
from cortex import frontmatter as fm
from cortex.kb import common as kb_common
from cortex.kb import index as kb_index
from cortex import model
from cortex.errors import CortexError
from cortex.lint.checks import OKF_ENTRY
from cortex.okf import links
from cortex.sanitize import sanitize

# OKF §8 lets a bundle-root index declare the format version, the one exception
# to index files carrying no frontmatter. It is the only place a recipient can
# read what they are holding, so an export says it.
OKF_VERSION = "0.2"

# `generated: {by, at}` (§5) as a nested block. `frontmatter.read_field` is flat
# by design -- it reads what cortex writes -- so this is the one place that
# walks into a mapping.
_GENERATED = re.compile(r"^generated:\s*$")
_GENERATED_SUB = re.compile(r"^\s+(by|at):\s*(.*)$")
_ISO_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True)
class Concept:
    """One bundle concept, already sanitized, in store terms."""
    slug: str
    title: str
    type: str
    description: str
    author: str
    created: str
    updated: str
    extra: list                 # unknown frontmatter lines, verbatim
    body: str
    source: str                 # bundle-relative path, for the listing


@dataclass
class ReadResult:
    concepts: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _generated(block: str) -> dict:
    """The `by` / `at` of a §5 `generated:` mapping, or an empty dict."""
    out, inside = {}, False
    for line in block.split("\n"):
        if _GENERATED.match(line):
            inside = True
            continue
        if not inside:
            continue
        m = _GENERATED_SUB.match(line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"\'')
        elif not line.startswith((" ", "\t")):
            break                       # the mapping ended at the next key
        # An indented key that is neither `by` nor `at` is somebody else's
        # provenance field; it is skipped, not read as the end of the mapping,
        # so a `generated:` block that orders them `by, model, at` keeps `at`.
    return out


def _date(value: str, fallback: str) -> str:
    """The `YYYY-MM-DD` inside an ISO 8601 timestamp, else FALLBACK."""
    m = _ISO_DATE.search(value or "")
    return m.group(1) if m else fallback


def read_bundle(root: Path) -> ReadResult:
    """Every concept in ROOT, sanitized and translated into store terms.

    Nested directories flatten: `knowledge/` is flat, so a concept is addressed
    by its stem, and two files sharing one stem keep the first (the shallower,
    then alphabetical) with a warning. That is `kb ingest`'s rule for the same
    situation, and the reason is the same: the alternative is inventing a slug
    the author never wrote."""
    if not root.is_dir():
        raise CortexError(f"bundle not found: {root}")

    files = sorted((p for p in root.rglob("*.md")
                    if p.is_file() and not model.is_reserved(p.name)),
                   key=lambda p: (len(p.relative_to(root).parts), str(p)))

    res, seen = ReadResult(), {}
    for path in files:
        rel = sanitize(path.relative_to(root).as_posix())
        slug = path.stem
        if not kb_common.SLUG.match(slug):
            res.warnings.append(f"invalid slug, skipping: {rel}")
            continue
        if slug in seen:
            res.warnings.append(f"duplicate concept {slug}, keeping {seen[slug]}, "
                                f"skipping {rel}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            res.warnings.append(f"cannot read {rel}: {e}")
            continue
        seen[slug] = rel
        res.concepts.append(_concept(slug, text, rel))

    stems = {c.slug for c in res.concepts}
    res.concepts = [_relink(c, stems.__contains__) for c in res.concepts]
    for c in res.concepts:
        if not c.type:
            # §11 makes `type` the one required field, so this bundle is not
            # conformant. Reported rather than refused: dropping the concept
            # loses content over a field `cortex kb update --type` can add,
            # and `kb lint --check okf` already lists exactly these.
            res.warnings.append(f"no type: field (OKF §11) in {c.source}; "
                                f"set one with cortex kb update --type")
    return res


def _concept(slug: str, text: str, rel: str) -> Concept:
    block, body = fm.split(text)
    if block is None:
        # No frontmatter at all: the whole file is the body. `fm.split` reports
        # (None, None) for that, and taking its `body` would silently import an
        # empty doc over somebody's writing. The export side makes the same
        # choice in `_store_docs`, for the same reason.
        body = text
    block = sanitize(block or "")
    gen = _generated(block)
    when = _date(gen.get("at", ""), kb_common.today())
    author = gen.get("by", "")
    return Concept(
        slug=slug,
        title=fm.read_field(block, "title"),
        type=fm.read_field(block, "type"),
        description=fm.read_field(block, "description"),
        # cortex's `author` is a two-value field (human | agent), so a
        # generator's name cannot go in it. The `generated:` block rides
        # through in `extra`, which is what actually preserves that provenance.
        author=author if author in ("human", "agent") else kb_common.AUTHOR_DEFAULT,
        # §5 calls `generated.at` "the content's last meaningful change", which
        # is what `updated` means here -- but a bundle cortex exported carries
        # both fields already, so its own win. Neither is stamped with today:
        # an import is not a re-verification, and stamping would blind
        # `kb lint --check stale` on every doc it touched, which is the same
        # reason #59 keeps a retype away from `kb update`. A bundle full of
        # 2024 docs should read as stale, because it is.
        created=_date(fm.read_field(block, "created"), when),
        updated=_date(fm.read_field(block, "updated"), when),
        extra=fm.unknown_lines(block),
        body=sanitize(body or ""),
        source=rel,
    )


def _relink(c: Concept, is_doc) -> Concept:
    """A second pass, because a link is only translatable once every concept in
    the bundle is known: the first doc read may link to the last."""
    return replace(c, body=links.to_wikilinks(c.body, is_doc))


# ---- export ----

@dataclass
class ExportResult:
    out: Path
    docs: int = 0
    logged: bool = False           # False when the store has no git history
    findings: list = field(default_factory=list)   # §11 violations in the output


def _store_docs(kdir: Path) -> list[tuple[str, str, "str | None", str]]:
    """(slug, title, frontmatter block, body) per non-reserved doc in KDIR.

    The frontmatter block travels verbatim. Re-rendering it through
    `fm.emit` would reorder a hand-written doc's keys and requote its values
    for no gain: the doc is already the store's own bytes, and preserving those
    is the thing cortex exists to do.

    `block` is None for a doc that has no frontmatter at all. Such a doc is not
    a §11 concept, but it is somebody's writing, so it travels whole and
    `validate` is what refuses the bundle. Dropping it would lose a body to
    make an export succeed, which is the wrong trade in both directions."""
    out = []
    for path in sorted(kdir.glob("*.md")):
        if model.is_reserved(path.name):
            continue
        text = path.read_text(encoding="utf-8")
        block, body = fm.split(text)
        out.append((path.stem, fm.read_field(block or "", "title"),
                    block, text if block is None else (body or "")))
    return out


def export_bundle(kdir: Path, out: Path, *, since: str = "") -> ExportResult:
    """Write KDIR as a self-contained OKF bundle at OUT.

    OUT must not already hold files. A bundle is defined by what is in the
    directory, so exporting over somebody else's files would produce one that
    claims concepts this store never had."""
    if out.exists() and not out.is_dir():
        raise CortexError(f"--out is not a directory: {out} "
                          f"(a bundle is a directory; pick a fresh one)")
    if out.is_dir() and any(out.iterdir()):
        raise CortexError(f"--out is not empty: {out} "
                          f"(a bundle is the whole directory; pick a fresh one)")
    docs = _store_docs(kdir)
    titles = {slug: title for slug, title, _b, _y in docs}

    def _resolve(ref):
        slug = ref.rsplit("/", 1)[-1]
        # A qualified reference names another workspace's doc, which this
        # bundle does not hold even when the slug happens to collide.
        if ref.count("/") > 1 or (ref.count("/") == 1
                                  and not ref.startswith("knowledge/")):
            return None
        return (slug, titles[slug]) if slug in titles else None

    out.mkdir(parents=True, exist_ok=True)
    for slug, _title, block, body in docs:
        text = links.to_markdown(body, _resolve)
        if block is not None:
            text = f"---\n{block}\n---\n\n{text}\n"
        atomic.write_text(out / f"{slug}.md", text, encoding="utf-8")

    res = ExportResult(out=out, docs=len(docs))
    atomic.write_text(out / kb_common.INDEX_NAME, "\n".join(_index_lines(kdir)) + "\n",
                      encoding="utf-8")
    res.logged = changelog.is_git_repo(kdir)
    hist = (changelog.read_history(kdir, since=since) if res.logged
            else changelog.History(entries=[], since=since))
    atomic.write_text(out / changelog.LOG_NAME,
                      "\n".join(changelog.render(kdir, hist, max_n=None, banner=False))
                      + "\n", encoding="utf-8")
    res.findings = validate(out)
    return res


def _index_lines(kdir: Path) -> list[str]:
    """The §8 index, rendered by the same function `kb index --write` uses, so
    a bundle's catalog and the store's cannot disagree about what exists.

    The frontmatter is §8's one exception to index files carrying none, and it
    is the only place a recipient can read which format version they hold."""
    return ["---", f"okf_version: {OKF_VERSION}", "---", "",
            "# Knowledge index", ""] + kb_index.render_section(kdir, None, okf=True)


def validate(out: Path) -> list[str]:
    """§11 against a bundle on disk: parseable frontmatter and a non-empty
    `type` on every non-reserved file, and §8 entries in the index.

    Run on the output rather than the input, because that is what ships. An
    export that cannot say its own bundle parses has not finished."""
    findings = []
    for path in sorted(out.rglob("*.md")):
        if model.is_reserved(path.name):
            continue
        block, _ = fm.split(path.read_text(encoding="utf-8"))
        rel = path.relative_to(out).as_posix()
        if block is None:
            findings.append(f"{rel}: no frontmatter block (§11)")
        elif not fm.read_field(block, "type").strip():
            findings.append(f"{rel}: no type: field (§11); "
                            f"set one with cortex kb update --type")
    index = out / kb_common.INDEX_NAME
    if index.is_file():
        _, body = fm.split(index.read_text(encoding="utf-8"))
        for n, line in enumerate((body or "").split("\n"), 1):
            stripped = line.strip()
            if (not stripped or stripped.startswith(("#", "<!--"))
                    or OKF_ENTRY.match(stripped)):
                continue
            findings.append(f"{kb_common.INDEX_NAME}:{n} is not a §8 entry: {stripped}")
            break
    return findings


def write_concepts(concepts, kdir: Path, *, write: bool) -> tuple[list, list]:
    """(created, skipped) for CONCEPTS against KDIR.

    Never overwrites: `kb new` is create-only for the same reason, and a bulk
    path has more to lose by clobbering than a single authored write does."""
    created, skipped = [], []
    for c in concepts:
        target = kdir / f"{c.slug}.md"
        if target.exists():
            skipped.append(c)
            continue
        created.append(c)
        if write:
            fields = {"title": c.title, "type": c.type, "author": c.author,
                      "created": c.created, "updated": c.updated,
                      "description": c.description}
            kdir.mkdir(parents=True, exist_ok=True)
            atomic.write_text(target, fm.emit(fields, c.body, extra=c.extra),
                              encoding="utf-8")
    return created, skipped
