"""Temporary re-export shim (removed in Phase 3 Task 2). Canonical: cortex.model."""
from cortex.model import *  # noqa: F401,F403
from cortex.model import (  # explicit for names not re-exported by *
    DocId, Doc, Edge, RawEdge, World, STATUS_OPEN, AUTHORED_EDGE_KINDS,
)
