"""Data model for parsed workspaces, sessions, and tasks."""
from dataclasses import dataclass, field

STATUS_OPEN = "open"
STATUS_IN_PROGRESS = "in_progress"
STATUS_BLOCKED = "blocked"
STATUS_RESOLVED = "resolved"
STATUS_UNKNOWN = "unknown"

ALL_STATUSES = (STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_BLOCKED, STATUS_RESOLVED, STATUS_UNKNOWN)


@dataclass
class Task:
    slug: str
    body: str = ""
    inline_fields: dict = field(default_factory=dict)
    blocked_by: list = field(default_factory=list)
    status: str = STATUS_UNKNOWN


@dataclass
class Session:
    slug: str
    summary_text: str = ""
    summary_meta: dict = field(default_factory=dict)
    active_agent_count: int = 0
    archived: bool = False
    tasks: list = field(default_factory=list)


@dataclass
class Workspace:
    slug: str
    has_meta: bool = False
    active_session_slugs: list = field(default_factory=list)
    sessions: list = field(default_factory=list)
