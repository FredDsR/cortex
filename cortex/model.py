"""Multi-typed graph model: every first-class doc is a node."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

STATUS_OPEN = "Open"
STATUS_IN_PROGRESS = "In Progress"
STATUS_BLOCKED = "Blocked"
STATUS_RESOLVED = "Resolved"
STATUS_UNKNOWN = None

ALL_STATUSES = (STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_BLOCKED, STATUS_RESOLVED)

NODE_KINDS = ("root", "workspace", "session", "task", "knowledge", "workbench")

# OKF v0.2 reserves §8 `index.md` and §9 `log.md` inside a bundle. A bundle is
# a `knowledge/` directory, and that is also the only place cortex derives
# either file, so the reservation stops there.
#
# It deliberately does not extend to `workbench/` or `tasks/`. Nothing is
# derived in those, so there is no file to collide with, and `log` is an
# entirely reasonable slug for a session scratch note. Treating it as reserved
# there would hide a real doc from the index, search and the viz to buy nothing.
#
# Inside `knowledge/` the reservation earns its keep twice over: a reserved file
# read back as knowledge would be listed in its own index, returned by `search`,
# drawn in the viz, and -- carrying no frontmatter by §8/§9 -- reported by
# `kb lint --check okf` as a doc with no `type`, against a file cortex wrote
# itself. And `kb index --write` / `kb log --write` would overwrite it.
#
# Kept here rather than in `kb` so the parser can share it without importing
# the command layer.
RESERVED_DOC_NAMES = frozenset({"index.md", "log.md"})

AUTHORED_EDGE_KINDS = ("blocked", "related", "follows", "mentions")
ALL_EDGE_KINDS = AUTHORED_EDGE_KINDS + ("contains",)


def is_reserved(name: str) -> bool:
    """True for a name reserved inside a `knowledge/` directory. Case-insensitive,
    so a legacy `INDEX.md` is excluded by the same rule as the lowercase one.

    Only meaningful for `knowledge/`; see RESERVED_DOC_NAMES for why callers
    walking `workbench/` or `tasks/` must not use it."""
    return name.lower() in RESERVED_DOC_NAMES


def format_description(description: Optional[str], title: Optional[str]) -> str:
    """Shared description fallback for knowledge/workbench rendering: the
    description, else the title, else a placeholder. One source of truth so the
    kb index CLI and the viz render description-less docs identically."""
    return (description or "") or (title or "") or "(no description)"


def group_by_type(items, type_of):
    """Group items by their `type` for the knowledge dictionary. Returns an
    ordered list of `(display_type, items)`: types are grouped and ordered
    case-insensitively (so `API` and `api` are one group), untyped ('') last.
    `display_type` is the first type string seen for that group (or '' when
    untyped). Callers own the per-group sorting and rendering."""
    groups: dict[str, list] = {}   # normalized key -> [display_type, items]
    for it in items:
        raw = type_of(it) or ""
        key = raw.lower()
        g = groups.get(key)
        if g is None:
            groups[key] = [raw, [it]]
        else:
            g[1].append(it)
    ordered = sorted(k for k in groups if k)
    if "" in groups:
        ordered.append("")
    return [(groups[k][0], groups[k][1]) for k in ordered]


@dataclass(frozen=True)
class DocId:
    """Canonical identifier for any first-class node."""
    kind: str
    workspace: Optional[str] = None
    session: Optional[str] = None
    slug: Optional[str] = None

    def canonical(self) -> str:
        if self.kind == "root":
            return "/"
        if self.kind == "workspace":
            return f"{self.workspace}/"
        if self.kind == "session":
            return f"{self.workspace}/{self.session}/"
        if self.kind == "task":
            return f"{self.workspace}/{self.session}/task/{self.slug}"
        if self.kind == "knowledge":
            return f"{self.workspace}/knowledge/{self.slug}"
        if self.kind == "workbench":
            return f"{self.workspace}/{self.session}/workbench/{self.slug}"
        raise ValueError(f"unknown DocId kind: {self.kind!r}")


@dataclass(frozen=True)
class RawEdge:
    """An authored relation before address resolution."""
    kind: str
    raw_target: str


@dataclass
class Doc:
    id: DocId
    title: str
    body: str
    frontmatter: dict
    rel_path: Optional[Path]
    edges_out: list = field(default_factory=list)
    ghost: bool = False
    status: Optional[str] = None
    archived: bool = False
    author: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    updated: Optional[str] = None


@dataclass
class Edge:
    source: DocId
    target: DocId
    raw_target: str
    kind: str
    resolved: bool = True


@dataclass
class World:
    root: Doc
    docs: dict
    edges: list = field(default_factory=list)
    ghosts: set = field(default_factory=set)
