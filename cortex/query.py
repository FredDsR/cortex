"""Graph queries over a parsed World. Pure: no disk IO (that lives in cli).

`neighbors` powers `cortex query neighbors <slug>`: progressive disclosure of a
doc's forward links, backlinks, and ghost (unresolved) references."""
from __future__ import annotations
from dataclasses import dataclass

from cortex.model import World, Doc, DocId, ALL_EDGE_KINDS
from cortex import address, parser

LINKABLE_KINDS = ("task", "knowledge", "workbench")
_KIND_ORDER = {k: i for i, k in enumerate(ALL_EDGE_KINDS)}


@dataclass
class Neighbor:
    kind: str
    doc_id: DocId
    address: str
    summary: str


@dataclass
class Ghost:
    kind: str
    raw_target: str


@dataclass
class NeighborResult:
    target: DocId
    outgoing: list
    backlinks: list
    ghosts: list
    outgoing_total: int
    backlinks_total: int


def _summary(doc: Doc) -> str:
    """One-line summary, first non-empty of description / title / status."""
    return doc.description or doc.title or doc.status or "(no summary)"


def _addr(doc_id: DocId, referencing: DocId) -> str:
    """Abbreviated address for linkable kinds; canonical id otherwise (e.g. a
    session reached via a `contains` backlink is not an abbreviate-able target)."""
    if doc_id.kind in LINKABLE_KINDS:
        return address.abbreviate(doc_id, referencing)
    return doc_id.canonical()


def _sort_key(n: Neighbor):
    return (_KIND_ORDER.get(n.kind, len(_KIND_ORDER)), n.address)


def _ghosts(world: World, target: DocId) -> list:
    doc = world.docs.get(target.canonical())
    if doc is None:
        return []
    out, seen = [], set()
    for raw in parser.raw_refs(doc):
        res = address.resolve(raw.raw_target, referencing=target)
        if res.resolved and res.doc_id.canonical() in world.docs:
            continue  # a real edge, not a ghost
        key = (raw.kind, raw.raw_target)
        if key in seen:
            continue
        seen.add(key)
        out.append(Ghost(kind=raw.kind, raw_target=raw.raw_target))
    return out


def neighbors(world: World, target_id: DocId, max: int = 20) -> NeighborResult:
    tcanon = target_id.canonical()
    outgoing, backlinks = [], []
    for e in world.edges:
        s, t = e.source.canonical(), e.target.canonical()
        if s == tcanon:
            tgt = world.docs.get(t)
            if tgt is not None:
                outgoing.append(Neighbor(e.kind, e.target,
                                         _addr(e.target, target_id), _summary(tgt)))
        if t == tcanon:
            src = world.docs.get(s)
            if src is not None:
                backlinks.append(Neighbor(e.kind, e.source,
                                          _addr(e.source, target_id), _summary(src)))
    outgoing.sort(key=_sort_key)
    backlinks.sort(key=_sort_key)
    return NeighborResult(
        target=target_id,
        outgoing=outgoing[:max],
        backlinks=backlinks[:max],
        ghosts=_ghosts(world, target_id),
        outgoing_total=len(outgoing),
        backlinks_total=len(backlinks),
    )


def find_by_slug(world: World, slug: str, *, workspace: str | None = None,
                 session: str | None = None) -> list:
    matches = []
    for doc in world.docs.values():
        did = doc.id
        if did.kind not in LINKABLE_KINDS or did.slug != slug:
            continue
        if workspace and did.workspace != workspace:
            continue
        if session and did.session != session:
            continue
        matches.append(doc)
    return sorted(matches, key=lambda d: d.id.canonical())
