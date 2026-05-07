"""Walk a `~/.work/workspaces/<slug>/` tree and produce a Workspace model."""
from pathlib import Path
import re

from .model import (
    Workspace, Session, Task, Edge, World,
    STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_BLOCKED, STATUS_RESOLVED, STATUS_UNKNOWN,
)


_FRONTMATTER_DELIM = "---\n"
_INLINE_FIELD_RE = re.compile(r"^\*\*([^*:]+?)(?::\*\*|\*\*:)\s*(.*)$")
_HEADING_RE = re.compile(r"^###\s+(.+?)\s*$")
_LINK_TASK_RE = re.compile(r"\[[^\]]+\]\(tasks/([a-z0-9-]+)\.md\)")
_BARE_TASK_RE = re.compile(r"\b(task-[a-z0-9-]+)\b")
_ARCHIVE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)$")

# Typed relations: one regex per kind, maps label -> kind tag.
# Pattern: optional leading whitespace, optional ** bold markers, label, optional colon, optional ** close bold.
_TYPED_REL_LABELS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\s*\*?\*?\s*Blocked by:?\s*\*?\*?\s*(.+)$", re.IGNORECASE), "blocked"),
    (re.compile(r"^\s*\*?\*?\s*Related to:?\s*\*?\*?\s*(.+)$", re.IGNORECASE), "related"),
    (re.compile(r"^\s*\*?\*?\s*Follows:?\s*\*?\*?\s*(.+)$", re.IGNORECASE), "follows"),
]

# Frontmatter snake_case keys -> internal kind tag.
_TYPED_REL_FM_KEYS: dict[str, str] = {
    "blocked_by": "blocked",
    "related_to": "related",
    "follows": "follows",
}

# Reference forms: bracketed slug (up to 2 slashes) and bare task-* slug (up to 2 slashes).
_REF_BRACKET_RE = re.compile(r"\[((?:[a-z0-9-]+/){0,2}[a-z0-9-]+)\]")
_REF_BARE_RE = re.compile(r"\b((?:[a-z0-9-]+/){0,2}task-[a-z0-9-]+)\b")

# Matches a complete line that begins a typed-relation declaration.
# Used by _parse_mentions to skip lines already handled by _parse_typed_relations.
_TYPED_REL_LINE_RE = re.compile(
    r"^\s*\*?\*?\s*(?:Blocked by|Related to|Follows)\b",
    re.IGNORECASE,
)

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
    body = text[end + 1 + len(_FRONTMATTER_DELIM):].lstrip("\n")
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


def _frontmatter_to_display(meta: dict) -> dict:
    """Convert YAML frontmatter keys (snake_case lowercase) to display form
    (Title Case with spaces) so the viz UI renders them like the legacy
    bold-pair labels. Empty values are dropped."""
    out: dict = {}
    for k, v in meta.items():
        if v is None or str(v).strip() == "":
            continue
        label = k.replace("_", " ").strip()
        label = " ".join(w.capitalize() for w in label.split())
        out[label] = str(v).strip()
    return out


_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")


def _extract_targets(rest: str) -> list[str]:
    """Extract all reference tokens from a relation line remainder.

    Strategy:
    1. Collect bracketed slug refs first (e.g. [task-foo], [feature-x/task-foo]).
       For full markdown links like [task-foo](tasks/task-foo.md) the bracket
       part is captured and the link is then erased so the URL is not re-matched.
    2. Erase full markdown links from a copy of rest before applying bare-slug
       matching, preventing the ``tasks/task-foo`` path segment from matching.
    3. Collect bare task-* refs not already captured.

    Tokens with three or more slashes are rejected by the regexes (max two
    slashes via {0,2}).
    """
    targets: list[str] = []
    seen: set[str] = set()
    for tok in _REF_BRACKET_RE.findall(rest):
        if tok not in seen:
            targets.append(tok)
            seen.add(tok)
    # Remove full markdown links before bare matching so the ``(url)`` part
    # is not picked up by _REF_BARE_RE.
    bare_rest = _MARKDOWN_LINK_RE.sub("", rest)
    for tok in _REF_BARE_RE.findall(bare_rest):
        if tok not in seen:
            targets.append(tok)
            seen.add(tok)
    return targets


def _parse_fm_list(value: str) -> list[str]:
    """Parse a frontmatter string value as a list.

    Accepts three forms:
    - Inline flow: ``[task-foo, task-bar]`` - strip brackets, split on commas.
    - Single string: ``task-foo`` - return as one-element list.
    - Empty string - return empty list.

    Block-form YAML lists are not handled here (``_split_frontmatter`` treats
    each ``- item`` as a separate key-less line which is skipped). Inline flow
    and single-string cover the documented usage.
    """
    v = value.strip()
    if not v:
        return []
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1]
        return [t.strip() for t in inner.split(",") if t.strip()]
    return [v]


def _parse_typed_relations(body: str, frontmatter: dict) -> list[tuple[str, str]]:
    """Return ``[(kind, raw_target), ...]`` for Blocked by / Related to / Follows.

    Sources are unioned with frontmatter first (in _TYPED_REL_FM_KEYS declaration
    order: blocked_by, related_to, follows), then body lines top-to-bottom.
    Duplicates on (kind, target) are suppressed.
    """
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(kind: str, target: str) -> None:
        pair = (kind, target)
        if pair not in seen:
            out.append(pair)
            seen.add(pair)

    # Frontmatter keys first.
    for fm_key, kind in _TYPED_REL_FM_KEYS.items():
        raw = frontmatter.get(fm_key, "")
        if not raw:
            continue
        for target in _parse_fm_list(str(raw)):
            if target:
                _add(kind, target)

    # Body lines.
    for line in body.splitlines():
        stripped = line.strip()
        for pattern, kind in _TYPED_REL_LABELS:
            m = pattern.match(stripped)
            if m:
                for target in _extract_targets(m.group(1)):
                    _add(kind, target)
                break  # one label per line

    return out


def _parse_blocked_by(body: str) -> list:
    """Back-compat shim: return a plain list of blocked-by slugs from body."""
    return [target for kind, target in _parse_typed_relations(body, {}) if kind == "blocked"]


def _strip_code_fences(body: str) -> str:
    """Return body with lines inside triple-backtick fences removed.

    Both the fence-delimiter lines and the content between them are dropped.
    Unbalanced fences cause everything from the unmatched opener to the end
    of the body to be treated as inside a fence (excluded).
    """
    out: list[str] = []
    in_fence = False
    for line in body.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue  # drop fence delimiter itself
        if in_fence:
            continue
        out.append(line)
    return "".join(out)


def _parse_mentions(body: str, typed_targets, source_slug: str) -> list[str]:
    """Return raw target strings mentioned in prose that are not typed relations.

    Arguments:
        body: raw task body text.
        typed_targets: iterable of raw target strings already captured by
            _parse_typed_relations; these are excluded from the output.
        source_slug: the task's own slug; self-references are excluded.

    Returns a deduped, first-seen-order list of raw target strings.
    """
    typed_set = set(typed_targets)
    seen: set[str] = set()
    result: list[str] = []

    stripped = _strip_code_fences(body)
    for line in stripped.splitlines():
        if _TYPED_REL_LINE_RE.match(line):
            continue
        # Collect bracketed refs then bare task-* refs (same strategy as _extract_targets).
        candidates: list[str] = []
        local_seen: set[str] = set()
        for tok in _REF_BRACKET_RE.findall(line):
            if tok not in local_seen:
                candidates.append(tok)
                local_seen.add(tok)
        bare_line = _MARKDOWN_LINK_RE.sub("", line)
        for tok in _REF_BARE_RE.findall(bare_line):
            if tok not in local_seen:
                candidates.append(tok)
                local_seen.add(tok)

        for tok in candidates:
            if tok == source_slug:
                continue
            if tok in typed_set:
                continue
            if tok not in seen:
                result.append(tok)
                seen.add(tok)

    return result


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
        if text and text not in slugs:
            slugs.append(text)
    return slugs


def _parse_session(sess_dir: Path, slug: str | None = None) -> Session:
    sess = Session(slug=slug or sess_dir.name)
    summary_path = sess_dir / "SUMMARY.md"
    if summary_path.exists():
        raw = summary_path.read_text(encoding="utf-8")
        meta, sess.summary_text = _split_frontmatter(raw)
        sess.summary_meta = _frontmatter_to_display(meta)
    sess.active_agent_count = _count_active(sess_dir)
    status_map = _parse_summary_status_map(sess.summary_text)
    tasks_dir = sess_dir / "tasks"
    if tasks_dir.exists():
        for task_path in sorted(tasks_dir.glob("*.md")):
            raw = task_path.read_text(encoding="utf-8")
            task_meta, body = _split_frontmatter(raw)
            t_slug = task_path.stem
            typed_rels = _parse_typed_relations(body, task_meta)
            typed_targets = [target for _, target in typed_rels]
            mentions = _parse_mentions(body, typed_targets, t_slug)
            edges = [Edge(source=t_slug, target=tgt, kind=kind, resolved=False)
                     for kind, tgt in typed_rels]
            edges += [Edge(source=t_slug, target=tgt, kind="mentions", resolved=False)
                      for tgt in mentions]
            inline = _parse_inline_fields(body)
            for k, v in _frontmatter_to_display(task_meta).items():
                inline[k] = v  # frontmatter wins over bold-pair
            status = status_map.get(t_slug)
            if status is None:
                status = _fallback_status_from_inline(inline.get("Status", ""))
            sess.tasks.append(Task(
                slug=t_slug,
                body=body,
                inline_fields=inline,
                blocked_by=[tgt for kind, tgt in typed_rels if kind == "blocked"],
                status=status,
                edges_out=edges,
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
    archive_dir = ws_dir / "archive"
    if archive_dir.exists():
        for ad in sorted(p for p in archive_dir.iterdir() if p.is_dir()):
            m = _ARCHIVE_DIR_RE.match(ad.name)
            archived_slug = m.group(1) if m else ad.name
            sess = _parse_session(ad, slug=archived_slug)
            sess.archived = True
            ws.sessions.append(sess)
    return ws


# ---------------------------------------------------------------------------
# parse_world: multi-workspace cross-WS edge resolution
# ---------------------------------------------------------------------------

def _list_workspace_slugs(workspaces_root: Path) -> list[str]:
    """Return sorted list of immediate subdirectory names under workspaces_root."""
    if not workspaces_root.is_dir():
        return []
    return sorted(p.name for p in workspaces_root.iterdir() if p.is_dir())


def _build_task_index(workspaces: list) -> dict:
    """Return a dict {canonical_id: Task} keyed by <ws>/<sess>/<task>.

    Only non-archived sessions are indexed for resolution purposes.
    """
    index: dict = {}
    for ws in workspaces:
        for sess in ws.sessions:
            if sess.archived:
                continue
            for task in sess.tasks:
                canonical = f"{ws.slug}/{sess.slug}/{task.slug}"
                index[canonical] = task
    return index


def _resolve_target(raw: str, src_ws: str, src_sess: str, index: dict) -> tuple[str, bool]:
    """Resolve a raw edge target to a canonical id.

    Returns (canonical_id, found) where found indicates membership in index.

    Resolution rules based on slash count in raw:
      0 slashes -> <src_ws>/<src_sess>/<raw>
      1 slash   -> <src_ws>/<raw>
      2 slashes -> <raw>  (already fully qualified)
      3+ slashes -> unresolvable; return (raw, False)
    """
    slash_count = raw.count("/")
    if slash_count == 0:
        canonical = f"{src_ws}/{src_sess}/{raw}"
    elif slash_count == 1:
        canonical = f"{src_ws}/{raw}"
    elif slash_count == 2:
        canonical = raw
    else:
        return raw, False
    return canonical, canonical in index


def parse_world(workspaces_root: Path) -> World:
    """Parse all workspaces under workspaces_root and resolve cross-WS edges.

    Returns a World with:
      - workspaces: all parsed Workspace objects
      - edges: flat list of all Edge objects (resolved and unresolved)
      - ghosts: deduplicated list of canonical IDs that could not be resolved
    """
    workspaces_root = Path(workspaces_root).resolve()
    slugs = _list_workspace_slugs(workspaces_root)
    workspaces = [parse_workspace(workspaces_root, slug) for slug in slugs]
    index = _build_task_index(workspaces)

    all_edges: list = []
    ghosts_seen: set = set()
    ghosts: list = []

    for ws in workspaces:
        for sess in ws.sessions:
            if sess.archived:
                continue
            for task in sess.tasks:
                for edge in task.edges_out:
                    canonical, found = _resolve_target(
                        edge.target, ws.slug, sess.slug, index
                    )
                    edge.target = canonical
                    edge.resolved = found
                    if not found and canonical not in ghosts_seen:
                        ghosts_seen.add(canonical)
                        ghosts.append(canonical)
                    all_edges.append(edge)

    return World(workspaces=workspaces, edges=all_edges, ghosts=ghosts)
