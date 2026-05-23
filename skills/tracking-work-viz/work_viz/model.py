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
AUTHORED_EDGE_KINDS = ("blocked", "related", "follows", "mentions")
ALL_EDGE_KINDS = AUTHORED_EDGE_KINDS + ("contains",)


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
