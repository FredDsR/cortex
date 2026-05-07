# tracking-work-viz Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `work-viz` tool that turns `~/.work/workspaces/<slug>/` into a three-pane browser viewer (tree, graph, content), runnable as a one-shot HTML generator or as a watch-mode local server with live updates.

**Architecture:** New sibling skill at `skills/tracking-work-viz/`. A small Python package (`work_viz/`) parses one workspace into a JSON model. A generator inlines that model into a self-contained HTML page; a server variant serves the same UI plus a `/data.json` endpoint and an SSE channel that pushes change events when files under `~/.work/workspaces/<slug>/` are modified. The UI is vanilla JS with Cytoscape.js (graph, vendored) and `marked` (markdown rendering, vendored).

**Tech Stack:** Python 3.11+ stdlib only (no `pip install`), HTML/CSS/JS, Cytoscape.js + cytoscape-dagre, marked.js. Tests with pytest.

**Reference spec:** `docs/superpowers/specs/2026-05-05-tracking-work-viz-design.md`

---

## File Structure

```
skills/tracking-work-viz/
  SKILL.md                        # skill metadata + invocation guide
  README.md                       # human-facing overview and CLI examples
  bin/
    work-viz                      # entry-point shebang script
  work_viz/
    __init__.py
    model.py                      # dataclasses: Workspace, Session, Task + status constants
    parser.py                     # walk + parse ~/.work/workspaces/<slug>/
    generator.py                  # one-shot HTML render
    server.py                     # watch mode: HTTP + SSE
    cli.py                        # argparse + dispatch
  templates/
    index.html                    # main viewer (tree + graph + content)
    dashboard.html                # cross-workspace overview
  vendor/                         # populated by install.sh, gitignored
    cytoscape.min.js
    dagre.min.js
    cytoscape-dagre.min.js
    marked.min.js
  tests/
    conftest.py                   # pytest fixtures
    fixtures/sample_work/         # synthetic ~/.work/-shaped tree
    test_parser.py
    test_generator.py
    test_server.py
```

Modified at repo root: `install.sh`, `.gitignore`.

---

## Task 1: Skill scaffolding

**Files:**
- Create: `skills/tracking-work-viz/SKILL.md`
- Create: `skills/tracking-work-viz/README.md`
- Create: `skills/tracking-work-viz/work_viz/__init__.py`
- Create: `skills/tracking-work-viz/bin/work-viz`
- Create: `skills/tracking-work-viz/templates/index.html` (placeholder)
- Create: `skills/tracking-work-viz/templates/dashboard.html` (placeholder)
- Create: `skills/tracking-work-viz/tests/__init__.py`
- Create: `skills/tracking-work-viz/tests/conftest.py`
- Modify: `.gitignore`

- [ ] **Step 1: Create directory structure**

```bash
cd skills && mkdir -p tracking-work-viz/{work_viz,bin,templates,tests/fixtures,vendor}
touch tracking-work-viz/work_viz/__init__.py tracking-work-viz/tests/__init__.py
```

- [ ] **Step 2: Write `SKILL.md`**

```markdown
---
name: tracking-work-viz
description: Use when the user wants a visual overview of `~/.work/` sessions and tasks ("show me what's going on", "visualize my work", "open the dashboard"). Generates a browser-based tree+graph+content viewer for one workspace, or a cross-workspace dashboard. Read-only.
---

# tracking-work-viz

Generates a browser-based viewer for `~/.work/workspaces/<slug>/`.

## Invocation

The user-facing command is `work-viz`, installed by `install.sh` as `~/.work/bin/work-viz`. The user must have `~/.work/bin/` on their `PATH`.

- One-shot: `work-viz <workspace-slug>` writes `~/.work/viz/<slug>.html` and prints the path. Open in a browser to view.
- Watch: `work-viz <workspace-slug> --watch` starts a local server and opens the browser; the page auto-refreshes when files under the workspace change.
- Dashboard: `work-viz --workspace=all` writes `~/.work/viz/dashboard.html` with a row per workspace.
- JSON: `work-viz <workspace-slug> --json` prints the parsed model to stdout (debugging).

## When to invoke

Use this when the user is overwhelmed by their `~/.work/` content and asks for a visual overview, status snapshot, or dashboard. Always offer the watch mode if the user expects to keep the viewer open while they work.

## Read-only

This skill never edits anything under `~/.work/`. Editing tasks stays in the existing `tracking-work` flow.
```

- [ ] **Step 3: Write `README.md`**

```markdown
# tracking-work-viz

Browser-based viewer for `~/.work/workspaces/<slug>/`.

## Install

`./install.sh` from the repo root sets up the symlink and downloads vendored JS.

## Usage

    work-viz <slug>           # generate ~/.work/viz/<slug>.html
    work-viz <slug> --watch   # serve + auto-refresh
    work-viz --workspace=all  # cross-workspace dashboard
    work-viz <slug> --json    # parsed model as JSON (debug)

The viewer has three panes: tree (workspace > session > task), graph (Cytoscape with blocker edges), and content (rendered markdown). Both side panes are individually collapsible.
```

- [ ] **Step 4: Write `bin/work-viz` entry point**

```python
#!/usr/bin/env python3
"""Entry point for work-viz. Resolves through symlinks, then dispatches to work_viz.cli."""
import os
import sys

_here = os.path.dirname(os.path.realpath(__file__))
_pkg_parent = os.path.dirname(_here)
sys.path.insert(0, _pkg_parent)

from work_viz.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

```bash
chmod +x skills/tracking-work-viz/bin/work-viz
```

- [ ] **Step 5: Write template placeholders**

`skills/tracking-work-viz/templates/index.html`:

```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>work-viz</title></head>
<body>
  <main id="root">placeholder</main>
  <script>
    window.VIZ_MODE = "@@MODE@@";
    window.VIZ_DATA = @@DATA@@;
  </script>
</body>
</html>
```

`skills/tracking-work-viz/templates/dashboard.html`:

```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>work-viz: dashboard</title></head>
<body>
  <main id="root">placeholder</main>
  <script>
    window.VIZ_DATA = @@DATA@@;
  </script>
</body>
</html>
```

- [ ] **Step 6: Update `.gitignore`**

Append to `/home/fred/Workspace/agentic/tracking-work-skills/.gitignore`:

```
# vendored JS for tracking-work-viz (populated by install.sh)
skills/tracking-work-viz/vendor/
```

- [ ] **Step 7: Stub `work_viz/__init__.py`**

```python
"""work_viz: browser-based viewer for ~/.work/workspaces/."""
__version__ = "0.1.0"
```

- [ ] **Step 8: Verify structure**

Run: `ls -R skills/tracking-work-viz | head -40`
Expected: shows `SKILL.md`, `README.md`, `bin/work-viz`, `work_viz/__init__.py`, `templates/index.html`, `templates/dashboard.html`, `tests/`.

- [ ] **Step 9: Commit**

```bash
git add skills/tracking-work-viz .gitignore
git commit -m "feat(tracking-work-viz): scaffold new skill skeleton"
```

---

## Task 2: Model dataclasses + test fixture

**Files:**
- Create: `skills/tracking-work-viz/work_viz/model.py`
- Create: `skills/tracking-work-viz/tests/fixtures/sample_work/workspaces/demo/.meta`
- Create: `skills/tracking-work-viz/tests/fixtures/sample_work/workspaces/demo/.active.aaa111`
- Create: `skills/tracking-work-viz/tests/fixtures/sample_work/workspaces/demo/sessions/feature-x/SUMMARY.md`
- Create: `skills/tracking-work-viz/tests/fixtures/sample_work/workspaces/demo/sessions/feature-x/.active.aaa111`
- Create: `skills/tracking-work-viz/tests/fixtures/sample_work/workspaces/demo/sessions/feature-x/.active.bbb222`
- Create: `skills/tracking-work-viz/tests/fixtures/sample_work/workspaces/demo/sessions/feature-x/tasks/task-foo.md`
- Create: `skills/tracking-work-viz/tests/fixtures/sample_work/workspaces/demo/sessions/feature-x/tasks/task-bar.md`
- Create: `skills/tracking-work-viz/tests/fixtures/sample_work/workspaces/demo/sessions/feature-x/tasks/task-baz.md`
- Create: `skills/tracking-work-viz/tests/fixtures/sample_work/workspaces/demo/archive/2026-04-01-old-feature/SUMMARY.md`
- Create: `skills/tracking-work-viz/tests/test_model.py`

- [ ] **Step 1: Write `model.py`**

```python
"""Data model for parsed workspaces, sessions, and tasks."""
from dataclasses import dataclass, field
from typing import Optional

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
```

- [ ] **Step 2: Write fixture files**

`tests/fixtures/sample_work/workspaces/demo/.meta`:

```
slug=demo
created=2026-04-01
```

`tests/fixtures/sample_work/workspaces/demo/.active.aaa111`:

```
feature-x
```

`tests/fixtures/sample_work/workspaces/demo/sessions/feature-x/SUMMARY.md`:

````markdown
---
github: example/demo
---

# Session: Feature X

**Slug:** feature-x
**Started:** 2026-04-15
**Session status:** Active

## Tasks

### In Progress

- [task-foo](tasks/task-foo.md) — Building the foo subsystem.

### Open

- [task-bar](tasks/task-bar.md) — Pending design review.

### Blocked

- [task-baz](tasks/task-baz.md) — Blocked on upstream API.

### Resolved

_None yet._
````

`tests/fixtures/sample_work/workspaces/demo/sessions/feature-x/.active.aaa111` and `.active.bbb222`: empty files (the workspace-level mapping is what carries the session slug; session-level `.active.*` files exist as count markers).

`tests/fixtures/sample_work/workspaces/demo/sessions/feature-x/tasks/task-foo.md`:

```markdown
# Foo

**Status:** In Progress
**Started:** 2026-04-20

## Description

The foo task.
```

`task-bar.md`:

```markdown
# Bar

**Status:** Open
**Blocked by:** task-foo

## Description

Waits on foo.
```

`task-baz.md`:

```markdown
# Baz

**Status:** Blocked
**Blocked by:** [task-foo](tasks/task-foo.md), task-bar

## Description

Blocked task.
```

`tests/fixtures/sample_work/workspaces/demo/archive/2026-04-01-old-feature/SUMMARY.md`:

```markdown
# Session: Old Feature

**Slug:** old-feature
**Session status:** Archived

## Tasks

### Resolved

- [task-historic](tasks/task-historic.md) — Done.
```

- [ ] **Step 3: Write `tests/conftest.py`**

```python
"""pytest fixtures for work-viz tests."""
from pathlib import Path
import pytest


@pytest.fixture
def fixtures_root() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_work"


@pytest.fixture
def workspaces_root(fixtures_root: Path) -> Path:
    return fixtures_root / "workspaces"
```

- [ ] **Step 4: Write `tests/test_model.py`**

```python
from work_viz.model import (
    Task, Session, Workspace,
    STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_BLOCKED, STATUS_RESOLVED, STATUS_UNKNOWN,
    ALL_STATUSES,
)


def test_task_defaults():
    t = Task(slug="task-foo")
    assert t.slug == "task-foo"
    assert t.body == ""
    assert t.inline_fields == {}
    assert t.blocked_by == []
    assert t.status == STATUS_UNKNOWN


def test_session_defaults():
    s = Session(slug="feature-x")
    assert s.tasks == []
    assert s.active_agent_count == 0
    assert s.archived is False


def test_workspace_defaults():
    w = Workspace(slug="demo")
    assert w.sessions == []
    assert w.has_meta is False


def test_status_constants_unique():
    assert len(set(ALL_STATUSES)) == 5
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_model.py -v`
Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/tracking-work-viz
git commit -m "feat(tracking-work-viz): model dataclasses + test fixture tree"
```

---

## Task 3: Parser part 1 — enumeration and body capture

**Files:**
- Create: `skills/tracking-work-viz/work_viz/parser.py`
- Create: `skills/tracking-work-viz/tests/test_parser.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parser.py
from pathlib import Path
from work_viz.parser import parse_workspace


def test_enumerates_sessions_and_tasks(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    assert ws.slug == "demo"
    assert ws.has_meta is True
    sessions = [s for s in ws.sessions if not s.archived]
    assert len(sessions) == 1
    sess = sessions[0]
    assert sess.slug == "feature-x"
    assert len(sess.tasks) == 3
    slugs = {t.slug for t in sess.tasks}
    assert slugs == {"task-foo", "task-bar", "task-baz"}


def test_captures_task_body(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    foo = next(t for t in sess.tasks if t.slug == "task-foo")
    assert "The foo task." in foo.body
    assert foo.body.startswith("# Foo")


def test_captures_summary_text(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    assert "# Session: Feature X" in sess.summary_text
    assert sess.summary_meta.get("github") == "example/demo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_parser.py -v`
Expected: ImportError or 3 FAILs (parser module not yet implemented).

- [ ] **Step 3: Implement minimal parser**

```python
# work_viz/parser.py
"""Walk a `~/.work/workspaces/<slug>/` tree and produce a Workspace model."""
from pathlib import Path
import re

from .model import Workspace, Session, Task, STATUS_UNKNOWN


_FRONTMATTER_DELIM = "---\n"


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith(_FRONTMATTER_DELIM):
        return {}, text
    end = text.find("\n" + _FRONTMATTER_DELIM, len(_FRONTMATTER_DELIM))
    if end == -1:
        return {}, text
    fm_block = text[len(_FRONTMATTER_DELIM):end]
    body = text[end + 1 + len(_FRONTMATTER_DELIM):]
    meta: dict = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body


def _parse_session(sess_dir: Path, slug: str | None = None) -> Session:
    sess = Session(slug=slug or sess_dir.name)
    summary_path = sess_dir / "SUMMARY.md"
    if summary_path.exists():
        raw = summary_path.read_text(encoding="utf-8")
        sess.summary_meta, sess.summary_text = _split_frontmatter(raw)
    tasks_dir = sess_dir / "tasks"
    if tasks_dir.exists():
        for task_path in sorted(tasks_dir.glob("*.md")):
            body = task_path.read_text(encoding="utf-8")
            sess.tasks.append(Task(slug=task_path.stem, body=body, status=STATUS_UNKNOWN))
    return sess


def parse_workspace(workspaces_root: Path, slug: str) -> Workspace:
    ws_dir = workspaces_root / slug
    if not ws_dir.is_dir():
        raise FileNotFoundError(f"workspace not found: {ws_dir}")
    ws = Workspace(slug=slug, has_meta=(ws_dir / ".meta").exists())
    sessions_dir = ws_dir / "sessions"
    if sessions_dir.exists():
        for sd in sorted(p for p in sessions_dir.iterdir() if p.is_dir()):
            ws.sessions.append(_parse_session(sd))
    return ws
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_parser.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/tracking-work-viz
git commit -m "feat(tracking-work-viz): parser part 1 - enumeration + body capture"
```

---

## Task 4: Parser part 2 — inline fields, status, blocked_by, agent counts

**Files:**
- Modify: `skills/tracking-work-viz/work_viz/parser.py`
- Modify: `skills/tracking-work-viz/tests/test_parser.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_parser.py`:

```python
from work_viz.model import (
    STATUS_IN_PROGRESS, STATUS_OPEN, STATUS_BLOCKED, STATUS_RESOLVED,
)


def test_inline_fields_parsed(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    foo = next(t for t in sess.tasks if t.slug == "task-foo")
    assert foo.inline_fields["Status"] == "In Progress"
    assert foo.inline_fields["Started"] == "2026-04-20"


def test_status_from_summary_headings(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    by_slug = {t.slug: t.status for t in sess.tasks}
    assert by_slug["task-foo"] == STATUS_IN_PROGRESS
    assert by_slug["task-bar"] == STATUS_OPEN
    assert by_slug["task-baz"] == STATUS_BLOCKED


def test_blocked_by_extracted(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    bar = next(t for t in sess.tasks if t.slug == "task-bar")
    baz = next(t for t in sess.tasks if t.slug == "task-baz")
    assert bar.blocked_by == ["task-foo"]
    assert baz.blocked_by == ["task-foo", "task-bar"]


def test_active_agent_count(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    sess = next(s for s in ws.sessions if s.slug == "feature-x")
    assert sess.active_agent_count == 2


def test_workspace_active_session_slugs(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    assert "feature-x" in ws.active_session_slugs
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_parser.py -v`
Expected: 5 new tests FAIL (KeyError on inline_fields, status still UNKNOWN, blocked_by empty, agent count 0, active_session_slugs empty).

- [ ] **Step 3: Add helper functions and wire them into the parser**

Replace the contents of `work_viz/parser.py` with:

```python
"""Walk a `~/.work/workspaces/<slug>/` tree and produce a Workspace model."""
from pathlib import Path
import re

from .model import (
    Workspace, Session, Task,
    STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_BLOCKED, STATUS_RESOLVED, STATUS_UNKNOWN,
)


_FRONTMATTER_DELIM = "---\n"
_INLINE_FIELD_RE = re.compile(r"^\*\*([^*:]+):\*\*\s*(.*)$")
_HEADING_RE = re.compile(r"^###\s+(.+?)\s*$")
_LINK_TASK_RE = re.compile(r"\[[^\]]+\]\(tasks/([a-z0-9-]+)\.md\)")
_BARE_TASK_RE = re.compile(r"\b(task-[a-z0-9-]+)\b")
_BLOCKED_BY_RE = re.compile(r"^\s*\*?\*?\s*Blocked by:?\s*\*?\*?\s*(.+)$", re.IGNORECASE)

_HEADING_TO_STATUS = {
    "in progress": STATUS_IN_PROGRESS,
    "open": STATUS_OPEN,
    "blocked": STATUS_BLOCKED,
    "resolved": STATUS_RESOLVED,
}


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith(_FRONTMATTER_DELIM):
        return {}, text
    end = text.find("\n" + _FRONTMATTER_DELIM, len(_FRONTMATTER_DELIM))
    if end == -1:
        return {}, text
    fm_block = text[len(_FRONTMATTER_DELIM):end]
    body = text[end + 1 + len(_FRONTMATTER_DELIM):]
    meta: dict = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body


def _parse_inline_fields(body: str) -> dict:
    fields: dict = {}
    for line in body.splitlines():
        m = _INLINE_FIELD_RE.match(line)
        if m:
            key = m.group(1).strip()
            if key not in fields:
                fields[key] = m.group(2).strip()
    return fields


def _parse_blocked_by(body: str) -> list:
    out: list = []
    for line in body.splitlines():
        m = _BLOCKED_BY_RE.match(line.strip())
        if not m:
            continue
        rest = m.group(1)
        for slug in _LINK_TASK_RE.findall(rest):
            if slug not in out:
                out.append(slug)
        for slug in _BARE_TASK_RE.findall(rest):
            if slug not in out:
                out.append(slug)
    return out


def _parse_summary_status_map(summary_text: str) -> dict:
    status_map: dict = {}
    current: str | None = None
    for line in summary_text.splitlines():
        h = _HEADING_RE.match(line)
        if h:
            current = _HEADING_TO_STATUS.get(h.group(1).strip().lower())
            continue
        if current is None:
            continue
        for slug in _LINK_TASK_RE.findall(line):
            status_map[slug] = current
        for slug in _BARE_TASK_RE.findall(line):
            status_map.setdefault(slug, current)
    return status_map


def _fallback_status_from_inline(value: str) -> str:
    v = value.lower()
    if "resolved" in v or "closed" in v:
        return STATUS_RESOLVED
    if "in progress" in v:
        return STATUS_IN_PROGRESS
    if "blocked" in v:
        return STATUS_BLOCKED
    if v.strip():
        return STATUS_OPEN
    return STATUS_UNKNOWN


def _count_active(dir_path: Path) -> int:
    return sum(1 for f in dir_path.iterdir() if f.name.startswith(".active."))


def _read_active_session_slugs(ws_dir: Path) -> list:
    slugs: list = []
    for f in sorted(ws_dir.iterdir()):
        if not f.name.startswith(".active."):
            continue
        try:
            text = f.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            slugs.append(text)
    return slugs


def _parse_session(sess_dir: Path, slug: str | None = None) -> Session:
    sess = Session(slug=slug or sess_dir.name)
    summary_path = sess_dir / "SUMMARY.md"
    if summary_path.exists():
        raw = summary_path.read_text(encoding="utf-8")
        sess.summary_meta, sess.summary_text = _split_frontmatter(raw)
    sess.active_agent_count = _count_active(sess_dir)
    status_map = _parse_summary_status_map(sess.summary_text)
    tasks_dir = sess_dir / "tasks"
    if tasks_dir.exists():
        for task_path in sorted(tasks_dir.glob("*.md")):
            body = task_path.read_text(encoding="utf-8")
            t_slug = task_path.stem
            inline = _parse_inline_fields(body)
            status = status_map.get(t_slug)
            if not status:
                status = _fallback_status_from_inline(inline.get("Status", ""))
            sess.tasks.append(Task(
                slug=t_slug,
                body=body,
                inline_fields=inline,
                blocked_by=_parse_blocked_by(body),
                status=status,
            ))
    return sess


def parse_workspace(workspaces_root: Path, slug: str) -> Workspace:
    ws_dir = workspaces_root / slug
    if not ws_dir.is_dir():
        raise FileNotFoundError(f"workspace not found: {ws_dir}")
    ws = Workspace(slug=slug, has_meta=(ws_dir / ".meta").exists())
    ws.active_session_slugs = _read_active_session_slugs(ws_dir)
    sessions_dir = ws_dir / "sessions"
    if sessions_dir.exists():
        for sd in sorted(p for p in sessions_dir.iterdir() if p.is_dir()):
            ws.sessions.append(_parse_session(sd))
    return ws
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_parser.py -v`
Expected: 8 PASS (3 from Task 3 + 5 new).

- [ ] **Step 5: Commit**

```bash
git add skills/tracking-work-viz
git commit -m "feat(tracking-work-viz): parser - inline fields, status, blockers, agents"
```

---

## Task 5: Parser part 3 — archived sessions

**Files:**
- Modify: `skills/tracking-work-viz/work_viz/parser.py`
- Modify: `skills/tracking-work-viz/tests/test_parser.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_parser.py`:

```python
def test_archived_sessions_present(workspaces_root: Path):
    ws = parse_workspace(workspaces_root, "demo")
    archived = [s for s in ws.sessions if s.archived]
    assert len(archived) == 1
    s = archived[0]
    assert s.slug == "old-feature"
    assert s.archived is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_parser.py::test_archived_sessions_present -v`
Expected: FAIL (no archived sessions in the model).

- [ ] **Step 3: Add archive parsing**

In `work_viz/parser.py`, add this module-level constant near the other regexes:

```python
_ARCHIVE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)$")
```

Then extend `parse_workspace` (after the existing `if sessions_dir.exists():` block, before `return ws`):

```python
    archive_dir = ws_dir / "archive"
    if archive_dir.exists():
        for ad in sorted(p for p in archive_dir.iterdir() if p.is_dir()):
            m = _ARCHIVE_DIR_RE.match(ad.name)
            slug = m.group(1) if m else ad.name
            sess = _parse_session(ad, slug=slug)
            sess.archived = True
            ws.sessions.append(sess)
    return ws
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_parser.py -v`
Expected: 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/tracking-work-viz
git commit -m "feat(tracking-work-viz): parser - archived sessions"
```

---

## Task 6: CLI dispatcher with `--json`

**Files:**
- Create: `skills/tracking-work-viz/work_viz/cli.py`
- Create: `skills/tracking-work-viz/tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
import json
import subprocess
import sys
from pathlib import Path


def test_cli_json_output(workspaces_root: Path, tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable, "-c",
        "import sys; sys.path.insert(0, %r); "
        "from work_viz.cli import main; "
        "sys.exit(main(['--workspaces-root', %r, 'demo', '--json']))" % (
            str(repo_root), str(workspaces_root),
        ),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    payload = json.loads(r.stdout)
    assert payload["slug"] == "demo"
    assert any(s["slug"] == "feature-x" for s in payload["sessions"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_cli.py -v`
Expected: FAIL (cli module not present).

- [ ] **Step 3: Implement `cli.py`**

```python
"""Command-line entry point for work-viz."""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .parser import parse_workspace


DEFAULT_WORKSPACES_ROOT = Path.home() / ".work" / "workspaces"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work-viz", description="Browser-based viewer for ~/.work/.")
    p.add_argument("workspace", nargs="?", help="Workspace slug to render. Omit with --workspace=all.")
    p.add_argument("--workspace", dest="workspace_flag", help="Set to 'all' for the cross-workspace dashboard.")
    p.add_argument("--watch", action="store_true", help="Run in watch mode (local server + SSE).")
    p.add_argument("--json", dest="emit_json", action="store_true", help="Print parsed model JSON to stdout.")
    p.add_argument("--workspaces-root", type=Path, default=DEFAULT_WORKSPACES_ROOT,
                   help="Override the workspaces root (defaults to ~/.work/workspaces).")
    p.add_argument("--port", type=int, default=0, help="Watch-mode port (0 picks 8765..8775).")
    p.add_argument("--no-open", action="store_true", help="Watch mode: don't auto-open the browser.")
    return p


def main(argv: list | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.workspace_flag == "all" or args.workspace == "all":
        # Dashboard mode is wired in Task 17.
        print("dashboard mode not yet implemented", file=sys.stderr)
        return 2

    if not args.workspace:
        parser.error("workspace slug is required (or use --workspace=all)")

    if args.emit_json:
        ws = parse_workspace(args.workspaces_root, args.workspace)
        json.dump(asdict(ws), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.watch:
        # Wired in Task 14-16.
        print("watch mode not yet implemented", file=sys.stderr)
        return 2

    # Wired in Task 9.
    print("one-shot mode not yet implemented", file=sys.stderr)
    return 2
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/tracking-work-viz
git commit -m "feat(tracking-work-viz): CLI dispatcher with --json"
```

---

## Task 7: install.sh updates and vendor download

**Files:**
- Modify: `install.sh`

- [ ] **Step 1: Read current install.sh**

```bash
cat install.sh
```

- [ ] **Step 2: Append vendor download and symlink logic**

Append to `install.sh` (preserving its current behavior; the snippet below is additive). Idempotent: re-running is safe.

```bash
# --- tracking-work-viz install ---
VIZ_DIR="$HOME/.work/bin"
VIZ_VENDOR="$(dirname "$0")/skills/tracking-work-viz/vendor"

mkdir -p "$VIZ_DIR" "$VIZ_VENDOR"

# Symlink work-viz onto ~/.work/bin
ln -sf "$(cd "$(dirname "$0")" && pwd)/skills/tracking-work-viz/bin/work-viz" "$VIZ_DIR/work-viz"

# Vendored JS (only fetched if missing)
fetch_if_missing() {
  local dest="$1"
  local url="$2"
  if [ ! -s "$dest" ]; then
    echo "Fetching $(basename "$dest")"
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "$url" -o "$dest"
    elif command -v wget >/dev/null 2>&1; then
      wget -q "$url" -O "$dest"
    else
      echo "warning: neither curl nor wget available; skip $url" >&2
      return 1
    fi
  fi
}

fetch_if_missing "$VIZ_VENDOR/cytoscape.min.js"        "https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"
fetch_if_missing "$VIZ_VENDOR/dagre.min.js"            "https://unpkg.com/dagre@0.8.5/dist/dagre.min.js"
fetch_if_missing "$VIZ_VENDOR/cytoscape-dagre.min.js"  "https://unpkg.com/cytoscape-dagre@2.5.0/cytoscape-dagre.js"
fetch_if_missing "$VIZ_VENDOR/marked.min.js"           "https://unpkg.com/marked@12.0.2/marked.min.js"

# Copy vendor + templates to a stable runtime location used by the generator and server
RUNTIME_DIR="$HOME/.work/viz"
mkdir -p "$RUNTIME_DIR/vendor"
cp "$VIZ_VENDOR/"*.js "$RUNTIME_DIR/vendor/" 2>/dev/null || true

echo "tracking-work-viz: installed. Add $VIZ_DIR to PATH if not already, then run: work-viz <workspace>"
# --- end tracking-work-viz install ---
```

- [ ] **Step 3: Run install.sh**

Run: `bash install.sh`
Expected: vendor JS downloaded into `skills/tracking-work-viz/vendor/`, symlink created at `~/.work/bin/work-viz`, runtime vendor populated at `~/.work/viz/vendor/`.

- [ ] **Step 4: Smoke-test the CLI**

Run: `~/.work/bin/work-viz demo --workspaces-root skills/tracking-work-viz/tests/fixtures/sample_work/workspaces --json | head -5`
Expected: prints `{` followed by `"slug": "demo",` etc.

- [ ] **Step 5: Commit**

```bash
git add install.sh
git commit -m "feat(install): wire tracking-work-viz symlink + vendor fetch"
```

---

## Task 8: Generator one-shot output

**Files:**
- Create: `skills/tracking-work-viz/work_viz/generator.py`
- Modify: `skills/tracking-work-viz/work_viz/cli.py`
- Modify: `skills/tracking-work-viz/templates/index.html`
- Create: `skills/tracking-work-viz/tests/test_generator.py`

- [ ] **Step 1: Replace the index.html template stub with the full data-plumbing layer**

`templates/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>work-viz</title>
  <link rel="stylesheet" href="vendor/app.css">
</head>
<body>
  <header id="topbar"></header>
  <main id="layout">
    <aside id="tree-pane" class="pane"></aside>
    <section id="graph-pane" class="pane"></section>
    <article id="content-pane" class="pane"></article>
  </main>
  <script>
    window.VIZ_MODE = "@@MODE@@";
    window.VIZ_DATA = @@DATA@@;
  </script>
  <script src="vendor/cytoscape.min.js"></script>
  <script src="vendor/dagre.min.js"></script>
  <script src="vendor/cytoscape-dagre.min.js"></script>
  <script src="vendor/marked.min.js"></script>
  <script src="vendor/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_generator.py
import json
from pathlib import Path
from work_viz.generator import generate_one_shot


def test_one_shot_writes_self_contained_html(workspaces_root: Path, tmp_path: Path):
    out = generate_one_shot(workspaces_root, "demo", out_dir=tmp_path)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    # MODE marker is replaced
    assert "@@MODE@@" not in text
    assert '"static"' in text
    # DATA placeholder is replaced with valid JSON
    assert "@@DATA@@" not in text
    # The slug should appear in the embedded data
    assert '"slug": "demo"' in text or '"slug":"demo"' in text
    # Vendor links should be relative
    assert 'src="vendor/cytoscape.min.js"' in text
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_generator.py -v`
Expected: FAIL (generator module missing).

- [ ] **Step 4: Implement the generator**

```python
# work_viz/generator.py
"""Render a one-shot self-contained HTML viewer for a workspace."""
from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path

from .parser import parse_workspace


_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
DEFAULT_OUT_DIR = Path.home() / ".work" / "viz"


def _render(template_name: str, replacements: dict) -> str:
    raw = (_TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
    out = raw
    for key, value in replacements.items():
        out = out.replace(key, value)
    return out


def generate_one_shot(workspaces_root: Path, slug: str, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    ws = parse_workspace(workspaces_root, slug)
    payload = json.dumps(asdict(ws), ensure_ascii=False)
    html = _render("index.html", {
        '"@@MODE@@"': '"static"',
        "@@DATA@@": payload,
    })
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
```

- [ ] **Step 5: Wire one-shot mode into the CLI**

Replace the `# Wired in Task 9.` block in `work_viz/cli.py` with:

```python
    from .generator import generate_one_shot
    out = generate_one_shot(args.workspaces_root, args.workspace)
    print(out)
    return 0
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd skills/tracking-work-viz && python -m pytest -v`
Expected: all tests so far PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/tracking-work-viz
git commit -m "feat(tracking-work-viz): one-shot HTML generator"
```

---

## Task 9: UI part 1 — tree pane and content pane (no graph yet)

**Files:**
- Create: `skills/tracking-work-viz/templates/vendor/app.js`
- Create: `skills/tracking-work-viz/templates/vendor/app.css`
- Modify: `install.sh` (copy app.js / app.css to runtime vendor)

> Note: We keep `app.js` and `app.css` under `templates/vendor/` in the source repo (they are first-party, not third-party), and `install.sh` copies them alongside the third-party JS into `~/.work/viz/vendor/`. They are committed to the repo (vendor/ is gitignored only for fetched JS).

- [ ] **Step 1: Update `.gitignore` to keep app.js/app.css tracked**

Replace the `skills/tracking-work-viz/vendor/` rule in `.gitignore` with:

```
skills/tracking-work-viz/vendor/
!skills/tracking-work-viz/templates/vendor/
```

(Actually `templates/vendor/` is a different path from `vendor/`, so the rule above does not over-include. The rule already excluded only the top-level `vendor/`. No change needed if it's already specific.)

Verify: `git check-ignore -v skills/tracking-work-viz/templates/vendor/app.js` should print no match (file is not ignored).

- [ ] **Step 2: Write `templates/vendor/app.css`**

```css
:root {
  --pane-bg: #fafafa;
  --pane-border: #e0e0e0;
  --status-open: #999;
  --status-in-progress: #1976d2;
  --status-blocked: #d32f2f;
  --status-resolved: #388e3c;
  --status-unknown: #ccc;
  --content-bg: #fff;
  --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
}

* { box-sizing: border-box; }

html, body { margin: 0; padding: 0; height: 100%; font-family: var(--font-stack); font-size: 14px; }

#topbar {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 12px; border-bottom: 1px solid var(--pane-border);
  background: var(--pane-bg);
  height: 44px;
}

#topbar h1 { margin: 0; font-size: 14px; font-weight: 600; }
#topbar .spacer { flex: 1; }
#topbar button { padding: 4px 8px; border: 1px solid var(--pane-border); background: white; cursor: pointer; border-radius: 4px; }
#topbar select { padding: 4px; }

#layout {
  display: grid;
  grid-template-columns: 280px 1fr 420px;
  height: calc(100% - 44px);
}

#layout.tree-collapsed { grid-template-columns: 0 1fr 420px; }
#layout.graph-collapsed { grid-template-columns: 280px 1fr 420px; } /* graph hidden separately */

.pane { overflow: auto; border-right: 1px solid var(--pane-border); }
.pane:last-child { border-right: none; }

#tree-pane { background: var(--pane-bg); }
#tree-pane.hidden { display: none; }
#graph-pane.hidden { display: none; }

.tree-section { padding: 4px 8px; }
.tree-session { font-weight: 600; cursor: pointer; padding: 4px 0; user-select: none; }
.tree-session .caret { display: inline-block; width: 12px; }
.tree-task { cursor: pointer; padding: 2px 0 2px 24px; font-weight: 400; }
.tree-task.selected, .tree-session.selected { background: #fff3b0; }

.status-pill {
  display: inline-block; width: 10px; height: 10px; border-radius: 50%;
  margin-right: 6px; vertical-align: middle;
}
.status-pill.open { background: var(--status-open); }
.status-pill.in_progress { background: var(--status-in-progress); }
.status-pill.blocked { background: var(--status-blocked); }
.status-pill.resolved { background: var(--status-resolved); }
.status-pill.unknown { background: var(--status-unknown); }

.agent-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 0 6px;
  background: #1976d2;
  color: white;
  border-radius: 8px;
  font-size: 11px;
  vertical-align: middle;
}

#content-pane { background: var(--content-bg); padding: 16px; }
.content-fields {
  font-size: 12px;
  border-bottom: 1px solid var(--pane-border);
  padding-bottom: 8px;
  margin-bottom: 12px;
  display: flex; flex-wrap: wrap; gap: 12px;
}
.content-fields .field strong { color: #555; }

.archived-tag { color: #888; font-style: italic; margin-left: 6px; }
```

- [ ] **Step 3: Write `templates/vendor/app.js` (tree + content only)**

```js
// Entry point. Loads data, renders tree + content pane. Graph + watch wired later.

const STATUS_ORDER = ["in_progress", "open", "blocked", "resolved", "unknown"];

const state = {
  data: null,
  selection: null,        // { kind: "session"|"task", sessionSlug, taskSlug? }
  collapsedSessions: new Set(),
  hideClosed: false,
  showArchive: false,
  treeCollapsed: false,
  graphCollapsed: false,
};

async function loadData() {
  if (window.VIZ_MODE === "static") return window.VIZ_DATA;
  const r = await fetch("/data.json");
  return await r.json();
}

function visibleTasks(session) {
  let tasks = session.tasks;
  if (state.hideClosed) {
    tasks = tasks.filter(t => t.status !== "resolved");
  }
  return tasks;
}

function visibleSessions(ws) {
  return ws.sessions.filter(s => state.showArchive || !s.archived);
}

function renderTopbar() {
  const ws = state.data;
  const bar = document.getElementById("topbar");
  bar.innerHTML = "";
  const h = document.createElement("h1");
  h.textContent = `Workspace: ${ws.slug}`;
  bar.appendChild(h);

  const spacer = document.createElement("span"); spacer.className = "spacer"; bar.appendChild(spacer);

  const treeBtn = document.createElement("button");
  treeBtn.textContent = state.treeCollapsed ? "Show tree" : "Hide tree";
  treeBtn.onclick = () => { state.treeCollapsed = !state.treeCollapsed; render(); };
  bar.appendChild(treeBtn);

  const graphBtn = document.createElement("button");
  graphBtn.textContent = state.graphCollapsed ? "Show graph" : "Hide graph";
  graphBtn.onclick = () => { state.graphCollapsed = !state.graphCollapsed; render(); };
  bar.appendChild(graphBtn);

  const closedBtn = document.createElement("button");
  closedBtn.textContent = state.hideClosed ? "Show closed" : "Hide closed";
  closedBtn.onclick = () => { state.hideClosed = !state.hideClosed; render(); };
  bar.appendChild(closedBtn);

  const archBtn = document.createElement("button");
  archBtn.textContent = state.showArchive ? "Hide archive" : "Show archive";
  archBtn.onclick = () => { state.showArchive = !state.showArchive; render(); };
  bar.appendChild(archBtn);
}

function statusPill(status) {
  const span = document.createElement("span");
  span.className = `status-pill ${status}`;
  return span;
}

function renderTree() {
  const pane = document.getElementById("tree-pane");
  pane.classList.toggle("hidden", state.treeCollapsed);
  pane.innerHTML = "";

  for (const sess of visibleSessions(state.data)) {
    const sessRow = document.createElement("div");
    sessRow.className = "tree-session";
    if (state.selection && state.selection.kind === "session" && state.selection.sessionSlug === sess.slug) {
      sessRow.classList.add("selected");
    }
    const collapsed = state.collapsedSessions.has(sess.slug);
    const caret = document.createElement("span");
    caret.className = "caret";
    caret.textContent = collapsed ? "+" : "-";
    sessRow.appendChild(caret);
    sessRow.appendChild(statusPill(aggregateSessionStatus(sess)));
    sessRow.appendChild(document.createTextNode(sess.slug));
    if (sess.active_agent_count > 1) {
      const badge = document.createElement("span");
      badge.className = "agent-badge";
      badge.textContent = `${sess.active_agent_count} agents`;
      sessRow.appendChild(badge);
    }
    if (sess.archived) {
      const tag = document.createElement("span");
      tag.className = "archived-tag";
      tag.textContent = "(archived)";
      sessRow.appendChild(tag);
    }
    sessRow.onclick = (e) => {
      // Caret toggles expansion; clicking row selects.
      if (e.target === caret) {
        if (collapsed) state.collapsedSessions.delete(sess.slug);
        else state.collapsedSessions.add(sess.slug);
      } else {
        state.selection = { kind: "session", sessionSlug: sess.slug };
      }
      render();
    };
    pane.appendChild(sessRow);

    if (!collapsed) {
      for (const t of visibleTasks(sess)) {
        const taskRow = document.createElement("div");
        taskRow.className = "tree-task";
        if (state.selection && state.selection.kind === "task" &&
            state.selection.sessionSlug === sess.slug && state.selection.taskSlug === t.slug) {
          taskRow.classList.add("selected");
        }
        taskRow.appendChild(statusPill(t.status));
        taskRow.appendChild(document.createTextNode(t.slug));
        taskRow.onclick = () => {
          state.selection = { kind: "task", sessionSlug: sess.slug, taskSlug: t.slug };
          render();
        };
        pane.appendChild(taskRow);
      }
    }
  }
}

function aggregateSessionStatus(sess) {
  const statuses = sess.tasks.map(t => t.status);
  if (statuses.includes("in_progress")) return "in_progress";
  if (statuses.includes("blocked")) return "blocked";
  if (statuses.length && statuses.every(s => s === "resolved")) return "resolved";
  if (statuses.includes("open")) return "open";
  return "unknown";
}

function renderContent() {
  const pane = document.getElementById("content-pane");
  pane.innerHTML = "";
  if (!state.selection) {
    pane.textContent = "Select a session or task on the left.";
    return;
  }
  const sess = state.data.sessions.find(s => s.slug === state.selection.sessionSlug);
  if (!sess) { pane.textContent = "(no longer present)"; return; }

  if (state.selection.kind === "session") {
    const fields = document.createElement("div");
    fields.className = "content-fields";
    if (sess.summary_meta && Object.keys(sess.summary_meta).length) {
      for (const [k, v] of Object.entries(sess.summary_meta)) {
        const f = document.createElement("span");
        f.className = "field";
        f.innerHTML = `<strong>${k}:</strong> ${v}`;
        fields.appendChild(f);
      }
    }
    pane.appendChild(fields);
    const md = document.createElement("div");
    md.className = "markdown-body";
    md.innerHTML = window.marked.parse(sess.summary_text || "(empty SUMMARY.md)");
    pane.appendChild(md);
    rewriteIntraTaskLinks(md, sess.slug);
    return;
  }

  // task
  const task = sess.tasks.find(t => t.slug === state.selection.taskSlug);
  if (!task) { pane.textContent = "(task no longer present)"; return; }

  const fields = document.createElement("div");
  fields.className = "content-fields";
  for (const [k, v] of Object.entries(task.inline_fields)) {
    const f = document.createElement("span");
    f.className = "field";
    f.innerHTML = `<strong>${k}:</strong> ${v}`;
    fields.appendChild(f);
  }
  pane.appendChild(fields);
  const md = document.createElement("div");
  md.className = "markdown-body";
  md.innerHTML = window.marked.parse(task.body || "");
  pane.appendChild(md);
  rewriteIntraTaskLinks(md, sess.slug);
}

function rewriteIntraTaskLinks(rootEl, sessionSlug) {
  for (const a of rootEl.querySelectorAll("a")) {
    const href = a.getAttribute("href") || "";
    const m = href.match(/^tasks\/([a-z0-9-]+)\.md$/);
    if (m) {
      a.addEventListener("click", (ev) => {
        ev.preventDefault();
        state.selection = { kind: "task", sessionSlug, taskSlug: m[1] };
        render();
      });
    }
  }
}

function render() {
  renderTopbar();
  renderTree();
  // Graph wired in Task 11.
  renderContent();
}

(async function init() {
  state.data = await loadData();
  // default selection: first non-archived session
  const ws = state.data;
  const firstSess = ws.sessions.find(s => !s.archived);
  if (firstSess) state.selection = { kind: "session", sessionSlug: firstSess.slug };
  render();
})();
```

- [ ] **Step 4: Update install.sh to copy app.js + app.css to runtime vendor**

In `install.sh`, after the `fetch_if_missing` block, add:

```bash
# Copy first-party JS/CSS (committed in templates/vendor/) to the runtime vendor dir
SRC_VENDOR="$(dirname "$0")/skills/tracking-work-viz/templates/vendor"
if [ -d "$SRC_VENDOR" ]; then
  cp "$SRC_VENDOR/"*.js "$RUNTIME_DIR/vendor/" 2>/dev/null || true
  cp "$SRC_VENDOR/"*.css "$RUNTIME_DIR/vendor/" 2>/dev/null || true
fi
```

(The earlier `cp "$VIZ_VENDOR/"*.js "$RUNTIME_DIR/vendor/"` line copies third-party fetched JS; this new block copies first-party assets. Both are idempotent.)

- [ ] **Step 5: Re-run install.sh and the generator manually**

```bash
bash install.sh
work-viz demo --workspaces-root skills/tracking-work-viz/tests/fixtures/sample_work/workspaces
```

Expected: prints a path like `/home/fred/.work/viz/demo.html`.

- [ ] **Step 6: Manual UI smoke test**

Open the printed path in a browser. Expected:

- Topbar shows "Workspace: demo" and four buttons.
- Left pane lists `feature-x` (with a "2 agents" badge) and three tasks below it (`task-foo`, `task-bar`, `task-baz`) with status pills.
- Clicking a task populates the right pane with its rendered markdown body.
- Clicking the session row populates the right pane with the rendered SUMMARY.
- The center pane is still empty (graph wired in Task 11).
- "Hide tree" and "Hide graph" buttons toggle pane visibility.
- "Hide closed" and "Show archive" toggle correctly.

- [ ] **Step 7: Commit**

```bash
git add skills/tracking-work-viz install.sh
git commit -m "feat(tracking-work-viz): UI tree and content panes (no graph yet)"
```

---

## Task 10: UI part 2 — graph pane (Cytoscape)

**Files:**
- Modify: `skills/tracking-work-viz/templates/vendor/app.js`
- Modify: `skills/tracking-work-viz/templates/vendor/app.css`

- [ ] **Step 1: Add graph-specific CSS**

Append to `templates/vendor/app.css`:

```css
#graph-pane { padding: 0; }
#cy-host { width: 100%; height: 100%; }
```

- [ ] **Step 2: Implement `renderGraph` in app.js**

In `templates/vendor/app.js`, do three changes:

1. Add a global `cy` reference:

```js
let cy = null;  // Cytoscape instance, lazily created
```

2. Replace the `// Graph wired in Task 11.` line in `render()` with:

```js
  renderGraph();
```

3. Add `renderGraph` and `buildGraphElements` functions:

```js
function buildGraphElements(ws) {
  const elements = [];
  // Workspace node
  elements.push({ data: { id: `ws:${ws.slug}`, label: ws.slug, kind: "workspace" } });
  for (const sess of visibleSessions(ws)) {
    const sessId = `sess:${sess.slug}`;
    elements.push({
      data: {
        id: sessId,
        label: sess.slug + (sess.active_agent_count > 1 ? `  (${sess.active_agent_count})` : ""),
        kind: "session",
        status: aggregateSessionStatus(sess),
        archived: !!sess.archived,
      },
    });
    elements.push({ data: { id: `e:ws:${sess.slug}`, source: `ws:${ws.slug}`, target: sessId, kind: "contains" } });
    const tasks = visibleTasks(sess);
    for (const t of tasks) {
      const tId = `task:${sess.slug}:${t.slug}`;
      elements.push({
        data: { id: tId, label: t.slug, kind: "task", status: t.status, sessionSlug: sess.slug, taskSlug: t.slug },
      });
      elements.push({ data: { id: `e:c:${sess.slug}:${t.slug}`, source: sessId, target: tId, kind: "contains" } });
      for (const upstream of (t.blocked_by || [])) {
        const upstreamId = `task:${sess.slug}:${upstream}`;
        elements.push({
          data: { id: `e:b:${sess.slug}:${t.slug}:${upstream}`, source: upstreamId, target: tId, kind: "blocks" },
        });
      }
    }
  }
  return elements;
}

function renderGraph() {
  const pane = document.getElementById("graph-pane");
  pane.classList.toggle("hidden", state.graphCollapsed);
  if (state.graphCollapsed) return;

  if (!cy) {
    pane.innerHTML = '<div id="cy-host"></div>';
    cy = window.cytoscape({
      container: document.getElementById("cy-host"),
      style: [
        { selector: "node", style: { "label": "data(label)", "font-size": 11, "text-valign": "center", "color": "#fff" } },
        { selector: 'node[kind = "workspace"]', style: { "shape": "round-rectangle", "background-color": "#444", "color": "#fff", "padding": 8 } },
        { selector: 'node[kind = "session"]', style: { "shape": "round-rectangle", "background-color": "#1976d2" } },
        { selector: 'node[kind = "session"][status = "blocked"]', style: { "background-color": "#d32f2f" } },
        { selector: 'node[kind = "session"][status = "resolved"]', style: { "background-color": "#388e3c" } },
        { selector: 'node[kind = "session"][status = "open"]', style: { "background-color": "#888" } },
        { selector: 'node[archived = "true"]', style: { "opacity": 0.5 } },
        { selector: 'node[kind = "task"]', style: { "shape": "ellipse", "background-color": "#888" } },
        { selector: 'node[kind = "task"][status = "in_progress"]', style: { "background-color": "#1976d2" } },
        { selector: 'node[kind = "task"][status = "blocked"]', style: { "background-color": "#d32f2f" } },
        { selector: 'node[kind = "task"][status = "resolved"]', style: { "background-color": "#388e3c", "opacity": 0.6 } },
        { selector: 'node[kind = "task"][status = "open"]', style: { "background-color": "#999" } },
        { selector: ":selected", style: { "border-width": 3, "border-color": "#fdd835" } },
        { selector: "edge", style: { "width": 1.5, "line-color": "#bbb", "target-arrow-shape": "triangle", "target-arrow-color": "#bbb", "curve-style": "bezier" } },
        { selector: 'edge[kind = "blocks"]', style: { "line-color": "#d32f2f", "target-arrow-color": "#d32f2f", "line-style": "dashed" } },
      ],
      layout: { name: "dagre", rankDir: "TB" },
      elements: buildGraphElements(state.data),
    });
    cy.on("tap", "node", (ev) => {
      const d = ev.target.data();
      if (d.kind === "task") {
        state.selection = { kind: "task", sessionSlug: d.sessionSlug, taskSlug: d.taskSlug };
      } else if (d.kind === "session") {
        const slug = d.id.slice(5);
        state.selection = { kind: "session", sessionSlug: slug };
      }
      render();
    });
  } else {
    // Update elements without rebuilding (preserves zoom/pan).
    cy.json({ elements: buildGraphElements(state.data) });
    cy.layout({ name: "dagre", rankDir: "TB" }).run();
  }

  // Sync selection ring to graph.
  cy.nodes().unselect();
  if (state.selection) {
    const id = state.selection.kind === "task"
      ? `task:${state.selection.sessionSlug}:${state.selection.taskSlug}`
      : `sess:${state.selection.sessionSlug}`;
    const node = cy.getElementById(id);
    if (node && node.length) node.select();
  }
}
```

- [ ] **Step 3: Re-run install.sh and the generator**

```bash
bash install.sh
work-viz demo --workspaces-root skills/tracking-work-viz/tests/fixtures/sample_work/workspaces
```

- [ ] **Step 4: Manual UI smoke test**

Open `~/.work/viz/demo.html`. Expected:

- Center pane shows a Cytoscape graph: a workspace node, one session node (blue, "feature-x"), three task nodes color-coded by status.
- A red dashed edge connects `task-foo -> task-bar` (bar blocked by foo) and `task-foo -> task-baz`, `task-bar -> task-baz`.
- Clicking a task node updates the content pane and highlights the corresponding tree row.
- The "Hide graph" button hides the center pane and the layout shifts.

- [ ] **Step 5: Commit**

```bash
git add skills/tracking-work-viz
git commit -m "feat(tracking-work-viz): UI graph pane with Cytoscape + blocker edges"
```

---

## Task 11: Watch mode — server with SSE

**Files:**
- Create: `skills/tracking-work-viz/work_viz/server.py`
- Modify: `skills/tracking-work-viz/work_viz/cli.py`
- Modify: `skills/tracking-work-viz/templates/index.html`
- Create: `skills/tracking-work-viz/tests/test_server.py`

- [ ] **Step 1: Update `templates/index.html` to fetch data when in dynamic mode**

The template stays the same as in Task 8 except the `app.js` now handles both modes (already does). No template change needed beyond what's already there. Verify by re-reading: `cat templates/index.html` — confirm `window.VIZ_MODE = "@@MODE@@";` is still present.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_server.py
import json
import shutil
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from work_viz.server import VizServer


@pytest.fixture
def writable_workspaces(tmp_path: Path, workspaces_root: Path) -> Path:
    dest = tmp_path / "workspaces"
    shutil.copytree(workspaces_root, dest)
    return dest


def _start_server(workspaces_root: Path, slug: str) -> VizServer:
    srv = VizServer(workspaces_root=workspaces_root, slug=slug, port=0)
    srv.start()
    return srv


def test_server_serves_data_json(writable_workspaces: Path):
    srv = _start_server(writable_workspaces, "demo")
    try:
        url = f"http://127.0.0.1:{srv.port}/data.json"
        with urllib.request.urlopen(url, timeout=5) as r:
            payload = json.loads(r.read())
        assert payload["slug"] == "demo"
    finally:
        srv.stop()


def test_server_emits_sse_change_on_file_modification(writable_workspaces: Path):
    srv = _start_server(writable_workspaces, "demo")
    received = []
    stop_evt = threading.Event()

    def listen():
        url = f"http://127.0.0.1:{srv.port}/events"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                for raw in r:
                    if stop_evt.is_set():
                        break
                    line = raw.decode("utf-8").strip()
                    if line.startswith("data: "):
                        received.append(line[len("data: "):])
                        if len(received) >= 1:
                            break
        except Exception:
            pass

    t = threading.Thread(target=listen, daemon=True)
    t.start()
    time.sleep(0.3)  # let SSE handshake settle

    # Touch a task file
    task_path = writable_workspaces / "demo" / "sessions" / "feature-x" / "tasks" / "task-foo.md"
    task_path.write_text(task_path.read_text() + "\n<!-- touched -->\n")

    t.join(timeout=5)
    stop_evt.set()
    srv.stop()

    assert any("change" in m for m in received), f"received={received}"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_server.py -v`
Expected: FAIL (server module missing).

- [ ] **Step 4: Implement the server**

```python
# work_viz/server.py
"""Watch-mode HTTP server with SSE change notifications. Stdlib only."""
from __future__ import annotations
import json
import os
import socket
import threading
import time
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue, Empty
from typing import Optional

from .parser import parse_workspace
from .generator import _TEMPLATES_DIR


def _scan_mtimes(root: Path) -> dict:
    out: dict = {}
    if not root.is_dir():
        return out
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            p = Path(dirpath) / fn
            try:
                out[str(p)] = p.stat().st_mtime
            except OSError:
                pass
    return out


def _pick_port(preferred_range=(8765, 8775)) -> int:
    for port in range(preferred_range[0], preferred_range[1] + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    # Fall back to OS-assigned
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _SSEHub:
    """Fan-out hub: one queue per connected SSE client."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: list = []

    def register(self) -> Queue:
        q: Queue = Queue()
        with self._lock:
            self._clients.append(q)
        return q

    def unregister(self, q: Queue) -> None:
        with self._lock:
            try:
                self._clients.remove(q)
            except ValueError:
                pass

    def broadcast(self, event: str) -> None:
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            q.put(event)


class VizServer:
    """Threading HTTP server that serves the viewer UI plus /data.json and /events."""

    def __init__(self, workspaces_root: Path, slug: str, port: int = 0,
                 runtime_dir: Optional[Path] = None) -> None:
        self.workspaces_root = workspaces_root
        self.slug = slug
        self.port = port or _pick_port()
        self.runtime_dir = runtime_dir or (Path.home() / ".work" / "viz")
        self._hub = _SSEHub()
        self._server: Optional[ThreadingHTTPServer] = None
        self._serve_thread: Optional[threading.Thread] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _build_handler(self):
        hub = self._hub
        slug = self.slug
        workspaces_root = self.workspaces_root
        runtime_dir = self.runtime_dir
        templates_dir = _TEMPLATES_DIR

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args, **_kwargs):
                return  # quiet

            def do_GET(self):
                if self.path == "/" or self.path == "/index.html":
                    raw = (templates_dir / "index.html").read_text(encoding="utf-8")
                    html = raw.replace('"@@MODE@@"', '"dynamic"').replace("@@DATA@@", "null")
                    self._send_text(html, "text/html; charset=utf-8")
                    return
                if self.path == "/data.json":
                    ws = parse_workspace(workspaces_root, slug)
                    body = json.dumps(asdict(ws), ensure_ascii=False)
                    self._send_text(body, "application/json; charset=utf-8")
                    return
                if self.path == "/events":
                    self._serve_sse(hub)
                    return
                if self.path.startswith("/vendor/"):
                    rel = self.path[len("/vendor/"):]
                    fp = runtime_dir / "vendor" / rel
                    if fp.is_file():
                        ctype = "text/javascript" if fp.suffix == ".js" else "text/css"
                        self._send_bytes(fp.read_bytes(), ctype)
                        return
                self.send_error(HTTPStatus.NOT_FOUND)

            def _send_text(self, body: str, ctype: str):
                data = body.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _send_bytes(self, data: bytes, ctype: str):
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _serve_sse(self, hub: _SSEHub):
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                # Initial comment to flush headers
                try:
                    self.wfile.write(b": connected\n\n")
                    self.wfile.flush()
                except OSError:
                    return
                q = hub.register()
                try:
                    while True:
                        try:
                            event = q.get(timeout=15)
                            payload = f"event: change\ndata: {event}\n\n"
                            self.wfile.write(payload.encode("utf-8"))
                            self.wfile.flush()
                        except Empty:
                            try:
                                self.wfile.write(b": keepalive\n\n")
                                self.wfile.flush()
                            except OSError:
                                break
                        except OSError:
                            break
                finally:
                    hub.unregister(q)

        return Handler

    def _watch_loop(self):
        target = self.workspaces_root / self.slug
        prev = _scan_mtimes(target)
        debounce_until = 0.0
        while not self._stop_event.wait(1.0):
            now = _scan_mtimes(target)
            if now != prev:
                debounce_until = time.monotonic() + 0.25
                prev = now
            if debounce_until and time.monotonic() >= debounce_until:
                debounce_until = 0.0
                self._hub.broadcast("change")

    def start(self) -> None:
        Handler = self._build_handler()
        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.port = self._server.server_address[1]
        self._serve_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._serve_thread.start()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
```

- [ ] **Step 5: Wire `--watch` into the CLI**

Replace the `# Wired in Task 14-16.` block in `work_viz/cli.py` with:

```python
    if args.watch:
        from .server import VizServer
        srv = VizServer(workspaces_root=args.workspaces_root, slug=args.workspace,
                         port=args.port)
        srv.start()
        url = f"http://127.0.0.1:{srv.port}/"
        print(f"work-viz watch: serving {url}")
        if not args.no_open:
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception:
                pass
        try:
            while True:
                import time as _t
                _t.sleep(60)
        except KeyboardInterrupt:
            print("stopping")
        finally:
            srv.stop()
        return 0
```

- [ ] **Step 6: Add SSE listener to `app.js`**

In `templates/vendor/app.js`, replace the bottom `init` IIFE with:

```js
function attachLiveReload() {
  if (window.VIZ_MODE !== "dynamic" || typeof EventSource === "undefined") return;
  const es = new EventSource("/events");
  es.addEventListener("change", async () => {
    state.data = await loadData();
    render();
  });
  es.onerror = () => {
    // Browser will auto-retry. Optional: show a small indicator.
  };
}

(async function init() {
  state.data = await loadData();
  const ws = state.data;
  const firstSess = ws.sessions.find(s => !s.archived);
  if (firstSess) state.selection = { kind: "session", sessionSlug: firstSess.slug };
  render();
  attachLiveReload();
})();
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_server.py -v`
Expected: 2 PASS.

- [ ] **Step 8: Manual smoke test**

```bash
bash install.sh
work-viz demo --watch --workspaces-root skills/tracking-work-viz/tests/fixtures/sample_work/workspaces --no-open
```

In another terminal: `echo "" >> skills/tracking-work-viz/tests/fixtures/sample_work/workspaces/demo/sessions/feature-x/tasks/task-foo.md`. Open `http://127.0.0.1:<port>/` in a browser; the page should refresh task-foo's data within ~1.3s of the touch (1s poll + 0.25s debounce).

Stop with Ctrl-C.

- [ ] **Step 9: Commit**

```bash
git add skills/tracking-work-viz
git commit -m "feat(tracking-work-viz): watch mode (HTTP + SSE + live reload)"
```

---

## Task 12: Dashboard mode

**Files:**
- Modify: `skills/tracking-work-viz/work_viz/generator.py`
- Modify: `skills/tracking-work-viz/work_viz/cli.py`
- Modify: `skills/tracking-work-viz/templates/dashboard.html`
- Modify: `skills/tracking-work-viz/tests/test_generator.py`
- Create: `skills/tracking-work-viz/templates/vendor/dashboard.js`
- Create: `skills/tracking-work-viz/templates/vendor/dashboard.css`

- [ ] **Step 1: Build the dashboard template**

Replace `templates/dashboard.html` with:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>work-viz: dashboard</title>
  <link rel="stylesheet" href="vendor/dashboard.css">
</head>
<body>
  <header><h1>~/.work/ workspaces</h1></header>
  <main id="rows"></main>
  <script>
    window.VIZ_DASHBOARD_DATA = @@DATA@@;
  </script>
  <script src="vendor/dashboard.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write `dashboard.css`**

```css
body { font-family: -apple-system, sans-serif; margin: 0; padding: 16px; }
h1 { font-size: 16px; margin: 0 0 12px 0; }
.row { display: grid; grid-template-columns: 1fr 80px 80px 160px 80px; gap: 12px; padding: 8px; border-bottom: 1px solid #eee; align-items: center; }
.row:hover { background: #fafafa; }
.row a { text-decoration: none; color: #1976d2; font-weight: 600; }
.row .num { text-align: right; font-variant-numeric: tabular-nums; }
.row .ts { color: #666; font-size: 12px; }
.row .agents { color: #1976d2; }
```

- [ ] **Step 3: Write `dashboard.js`**

```js
(function () {
  const rows = document.getElementById("rows");
  const data = window.VIZ_DASHBOARD_DATA || { workspaces: [] };
  for (const ws of data.workspaces) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <a href="${ws.slug}.html">${ws.slug}</a>
      <span class="num">${ws.session_count} sess</span>
      <span class="num">${ws.task_count} tasks</span>
      <span class="ts">${ws.last_updated || ""}</span>
      <span class="agents">${ws.agent_count > 0 ? ws.agent_count + " agents" : ""}</span>
    `;
    rows.appendChild(row);
  }
})();
```

- [ ] **Step 4: Add the failing dashboard test**

Append to `tests/test_generator.py`:

```python
from work_viz.generator import generate_dashboard


def test_dashboard_lists_workspaces(workspaces_root: Path, tmp_path: Path):
    out = generate_dashboard(workspaces_root, out_dir=tmp_path)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "@@DATA@@" not in text
    assert '"slug": "demo"' in text or '"slug":"demo"' in text
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `cd skills/tracking-work-viz && python -m pytest tests/test_generator.py::test_dashboard_lists_workspaces -v`
Expected: FAIL (`generate_dashboard` not defined).

- [ ] **Step 6: Implement `generate_dashboard`**

In `work_viz/generator.py`, append:

```python
import datetime as _dt


def _summarize(workspaces_root: Path) -> dict:
    out = {"workspaces": []}
    if not workspaces_root.is_dir():
        return out
    for ws_dir in sorted(p for p in workspaces_root.iterdir() if p.is_dir()):
        slug = ws_dir.name
        ws = parse_workspace(workspaces_root, slug)
        session_count = len([s for s in ws.sessions if not s.archived])
        task_count = sum(len(s.tasks) for s in ws.sessions if not s.archived)
        last_mtime = 0.0
        for dp, _, fns in os.walk(ws_dir):
            for fn in fns:
                try:
                    mt = (Path(dp) / fn).stat().st_mtime
                    if mt > last_mtime:
                        last_mtime = mt
                except OSError:
                    pass
        last_iso = (
            _dt.datetime.fromtimestamp(last_mtime).strftime("%Y-%m-%d %H:%M")
            if last_mtime else ""
        )
        out["workspaces"].append({
            "slug": slug,
            "session_count": session_count,
            "task_count": task_count,
            "last_updated": last_iso,
            "agent_count": len(ws.active_session_slugs),
        })
    return out


def generate_dashboard(workspaces_root: Path, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    payload = json.dumps(_summarize(workspaces_root), ensure_ascii=False)
    html = _render("dashboard.html", {"@@DATA@@": payload})
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "dashboard.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
```

Also add `import os` at the top of `generator.py` if not already present.

- [ ] **Step 7: Wire `--workspace=all` into the CLI**

Replace the `print("dashboard mode not yet implemented", file=sys.stderr); return 2` block in `cli.py` with:

```python
        from .generator import generate_dashboard
        out = generate_dashboard(args.workspaces_root)
        print(out)
        return 0
```

- [ ] **Step 8: Run all tests**

Run: `cd skills/tracking-work-viz && python -m pytest -v`
Expected: all PASS.

- [ ] **Step 9: Manual smoke test**

```bash
bash install.sh
work-viz --workspace=all --workspaces-root skills/tracking-work-viz/tests/fixtures/sample_work/workspaces
```

Open the printed dashboard.html. Expected: one row for `demo` linking to `demo.html`, with session/task counts.

- [ ] **Step 10: Commit**

```bash
git add skills/tracking-work-viz
git commit -m "feat(tracking-work-viz): dashboard mode for cross-workspace overview"
```

---

## Task 13: End-to-end smoke against real `~/.work/`

**Files:**
- None modified. This task verifies the tool works against the user's actual data.

- [ ] **Step 1: Generate one-shot for each real workspace**

```bash
for slug in $(ls ~/.work/workspaces); do
  echo "--- $slug ---"
  work-viz "$slug" || echo "FAILED: $slug"
done
```

Expected: each prints `~/.work/viz/<slug>.html`. Open the OPTX-AI one in a browser; verify:

- Tree shows `chatbot-backend` and `infra-work` sessions, with their task counts.
- `infra-work` shows a "2 agents" badge (it has two `.active.*` files).
- Status pills correctly mark Resolved tasks (greyed).
- Graph renders without overflowing; blocker edges (if any) appear dashed.

- [ ] **Step 2: Try the dashboard**

```bash
work-viz --workspace=all
```

Open `~/.work/viz/dashboard.html`. Expected: a row per real workspace, last-updated timestamps reflecting actual file mtimes, click-throughs work.

- [ ] **Step 3: Try watch mode against a real workspace**

```bash
work-viz psgequity-OPTX-AI --watch &
```

Touch a file: `touch ~/.work/workspaces/psgequity-OPTX-AI/sessions/chatbot-backend/SUMMARY.md`. The browser tab should refresh its data within ~1.3s without losing the currently-selected task. `kill %1` to stop.

- [ ] **Step 4: Note any quirks for follow-up**

If anything looks wrong (overflowing graph layout for large workspaces, slow polling, parser misclassifying a task), capture details for a follow-up task. Do not fix in this plan; the spec covers v1 only.

- [ ] **Step 5: Commit (no code, but a README update if anything is worth flagging)**

If everything works, commit nothing. If small README polish is needed:

```bash
git add skills/tracking-work-viz/README.md
git commit -m "docs(tracking-work-viz): tweaks from real-workspace smoke test"
```

---

## Self-review pass (writer's checklist)

After completing all tasks, run through this once:

- [ ] All tests pass: `cd skills/tracking-work-viz && python -m pytest -v`
- [ ] `work-viz` is on `PATH` via `~/.work/bin/work-viz` symlink
- [ ] Vendor JS is fetched into `~/.work/viz/vendor/`
- [ ] One-shot, watch, and dashboard modes each open a working page in a browser
- [ ] Spec coverage: every section of `2026-05-05-tracking-work-viz-design.md` maps to at least one task above (parser -> Tasks 3-5; generator -> Task 8; UI -> Tasks 9-10; server -> Task 11; dashboard -> Task 12; install -> Task 7)
- [ ] No `git add` of anything under `docs/superpowers/` (per project policy)
