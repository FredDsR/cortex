"""cortex kb ingest: extract documentable artifacts from a codebase into
knowledge docs. Deterministic OpenAPI + SQL DDL extraction; fuzzy sources go to
an agent worklist. Moved from the former lib/ingest_extract.py; the extractor is
now called in-process (concept dicts, no wire format), collecting diagnostics
into a warnings list instead of stderr.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

from cortex import frontmatter as fm
from cortex import store
from cortex.errors import CortexError
from cortex.kb import _home, sync_after, today

try:
    import yaml  # noqa
    _HAVE_YAML = True
except Exception:
    _HAVE_YAML = False

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_PRUNE = {".git", "node_modules", ".work"}


# ---- extractor (pure) ----

def slugify(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "x"


def _dedupe(xs):
    seen, out = set(), []
    for x in xs:
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out


def _oneline(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def _type_str(pdef, links):
    if not isinstance(pdef, dict):
        return "any"
    ref = pdef.get("$ref")
    if isinstance(ref, str):
        name = ref.split("/")[-1]
        links.append(f"schema-{slugify(name)}")
        return name
    t = pdef.get("type", "any")
    if t == "array":
        return f"array of {_type_str(pdef.get('items', {}), links)}"
    return t


def _collect_refs(node, links):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str) and ("/schemas/" in v or "/definitions/" in v):
                links.append(f"schema-{slugify(v.split('/')[-1])}")
            else:
                _collect_refs(v, links)
    elif isinstance(node, list):
        for x in node:
            _collect_refs(x, links)


def extract_openapi(path, data):
    recs = []
    if not isinstance(data, dict):
        return recs
    schemas = ((data.get("components") or {}).get("schemas")) or data.get("definitions") or {}
    for name, sch in (schemas or {}).items():
        links = []
        props = (sch or {}).get("properties", {}) or {}
        lines = [f"# {name}", "", "Schema.", ""]
        for pname, pdef in props.items():
            lines.append(f"- `{pname}`: {_type_str(pdef, links)}")
        recs.append(dict(slug=f"schema-{slugify(name)}", type="Reference",
                         title=str(name), description=f"Schema {name}",
                         links=_dedupe(links), body="\n".join(lines), source=path))
    for p, item in (data.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(op, dict):
                continue
            title = f"{method.upper()} {p}"
            desc = _oneline(op.get("summary") or op.get("description") or title)
            links = []
            _collect_refs(op, links)
            body = f"# {title}\n\n{op.get('summary', '')}".rstrip()
            recs.append(dict(slug=f"op-{slugify(method + '-' + p)}", type="API",
                             title=title, description=desc,
                             links=_dedupe(links), body=body, source=path))
    return recs


def _strip_sql_comments(text):
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "'":
                if i + 1 < n and text[i + 1] == "'":
                    out.append("'"); i += 2; continue
                in_str = False
            i += 1; continue
        if c == "'":
            in_str = True; out.append(c); i += 1; continue
        if c == "-" and i + 1 < n and text[i + 1] == "-":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2; continue
        out.append(c); i += 1
    return "".join(out)


def _split_top_commas(s):
    parts, depth, cur, in_str = [], 0, "", False
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if in_str:
            cur += c
            if c == "'":
                if i + 1 < n and s[i + 1] == "'":
                    cur += "'"; i += 2; continue
                in_str = False
            i += 1; continue
        if c == "'":
            in_str = True; cur += c; i += 1; continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == "," and depth == 0:
            parts.append(cur); cur = ""
        else:
            cur += c
        i += 1
    if cur.strip():
        parts.append(cur)
    return parts


_CONSTRAINT_KW = {"PRIMARY", "FOREIGN", "CONSTRAINT", "UNIQUE", "CHECK", "KEY", "INDEX"}


def _table_concept(path, name, body_sql):
    cols, links = [], []
    for part in _split_top_commas(body_sql):
        p = part.strip()
        if not p:
            continue
        mref = re.search(r"references\s+([`\"\[]?[\w.]+[`\"\]]?)", p, re.IGNORECASE)
        if mref:
            ref_name = mref.group(1).strip('`"[]')
            links.append(f"table-{slugify(ref_name)}")
        kw = p.split(None, 1)[0].upper().strip('`"[]')
        if kw in _CONSTRAINT_KW:
            continue
        toks = p.split(None, 1)
        cname = toks[0].strip('`"[]')
        ctype = _oneline(toks[1]) if len(toks) > 1 else ""
        cols.append((cname, ctype))
    lines = [f"# {name}", "", "| column | type |", "|--------|------|"]
    for c, t in cols:
        lines.append(f"| `{c}` | `{t}` |")
    return dict(slug=f"table-{slugify(name)}", type="Reference", title=str(name),
                description=f"Table {name} ({len(cols)} columns)",
                links=_dedupe(links), body="\n".join(lines), source=path)


def _match_paren(text, popen):
    depth, i, n, in_str = 0, popen, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            if c == "'":
                if i + 1 < n and text[i + 1] == "'":
                    i += 2; continue
                in_str = False
            i += 1; continue
        if c == "'":
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def extract_sql(path, text, warnings=None):
    text = _strip_sql_comments(text)
    low = text.lower()
    recs, idx = [], 0
    while True:
        m = re.search(r"create\s+table\s+(if\s+not\s+exists\s+)?", low[idx:])
        if not m:
            break
        start = idx + m.end()
        nm = re.match(r"\s*([`\"\[]?[\w.]+[`\"\]]?)", text[start:])
        if not nm:
            idx = start + 1
            continue
        name = nm.group(1).strip('`"[]')
        popen = text.find("(", start)
        if popen == -1:
            break
        close = _match_paren(text, popen)
        if close == -1:
            if warnings is not None:
                warnings.append(f"unbalanced CREATE TABLE {name} in {path}, skipping")
            idx = start
            continue
        recs.append(_table_concept(path, name, text[popen + 1:close]))
        idx = close + 1
    return recs


def detect_and_extract(path, warnings=None):
    ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        if warnings is not None:
            warnings.append(f"cannot read {path}: {e}")
        return []
    if ext == "sql":
        return extract_sql(path, text, warnings)
    if ext == "json":
        try:
            data = json.loads(text)
        except Exception as e:
            if warnings is not None:
                warnings.append(f"cannot parse {path}: {e}")
            return []
    elif not _HAVE_YAML:
        if warnings is not None:
            warnings.append(f"PyYAML unavailable, skipping {path}")
        return []
    else:
        try:
            data = yaml.safe_load(text)
        except Exception as e:
            if warnings is not None:
                warnings.append(f"cannot parse {path}: {e}")
            return []
    if isinstance(data, dict) and ("openapi" in data or "swagger" in data or "paths" in data):
        return extract_openapi(path, data)
    return []


def extract_all(paths):
    """Extract concept dicts from all paths; returns (records, warnings).
    Dedupes by slug (first wins) and never aborts on one bad file."""
    records, warnings, seen = [], [], set()
    for path in paths:
        try:
            recs = detect_and_extract(path, warnings)
        except Exception as e:
            warnings.append(f"failed to extract {path}: {e}")
            continue
        for rec in recs:
            if rec["slug"] in seen:
                warnings.append(f"duplicate slug {rec['slug']} from {path}, skipping")
                continue
            seen.add(rec["slug"])
            records.append(rec)
    return records, warnings


# ---- orchestration ----

def _walk_files(src: Path):
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in _PRUNE]
        for fn in files:
            yield Path(root) / fn


def _discover_structured(src: Path, only) -> list[Path]:
    out = []
    for f in _walk_files(src):
        n = f.name.lower()
        ext = n.rsplit(".", 1)[-1] if "." in n else ""
        is_api = (n.startswith("openapi") or n.startswith("swagger")) and ext in ("yml", "yaml", "json")
        is_sql = n.endswith(".sql")
        if only != "sql" and is_api:
            out.append(f)
        elif only != "openapi" and is_sql:
            out.append(f)
    return sorted(out, key=str)


def _worklist(src: Path) -> list[str]:
    prisma, readme, runbook = [], [], []
    api_hdr = re.compile(r"^##[ \t]+(API|Schema)\b", re.MULTILINE)
    for f in _walk_files(src):
        n = f.name.lower()
        if n.endswith(".prisma"):
            prisma.append(f"{f} - Prisma schema")
        elif n.startswith("readme") and n.endswith(".md"):
            try:
                if api_hdr.search(f.read_text(encoding="utf-8", errors="replace")):
                    readme.append(f"{f} - has ## API/## Schema section")
            except OSError:
                pass
        elif n.startswith("runbook"):
            runbook.append(f"{f} - runbook")
    return sorted(prisma) + sorted(readme) + sorted(runbook)


def cmd_ingest(args) -> int:
    src = Path(args.src)
    if not src.is_dir():
        raise CortexError(f"--from path not found: {src}")
    if args.max < 0:
        raise CortexError("--max must be a non-negative integer")

    ws_root = store.resolve_workspace(args.workspace, home=_home(), cwd=Path.cwd())
    kdir = ws_root / "knowledge"

    structured = _discover_structured(src, args.only)
    records, warnings = extract_all([str(f) for f in structured])
    records.sort(key=lambda r: (r["type"], r["slug"]))   # type then slug (C order)

    now = today()
    create_lines, skip_lines = [], []
    count = overflow = 0
    for r in records:
        slug = r["slug"]
        if not _SLUG.match(slug):
            warnings.append(f"skipping record with invalid slug: {slug}")
            continue
        target = kdir / f"{slug}.md"
        line = f"{slug} [{r['type']}] - {r['description']}  <- {r['source']}"
        if target.exists():
            skip_lines.append(line)
            continue
        if count >= args.max:
            overflow += 1
            continue
        count += 1
        create_lines.append(line)
        if args.write:
            body = r["body"]
            if r["links"]:
                body += "\n\n## Related\n"
                for l in r["links"]:
                    body += f"\n- [[knowledge/{l}]]"
            fields = {"title": r["title"], "type": r["type"], "author": "agent",
                      "created": now, "updated": now, "description": r["description"]}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(fm.emit(fields, body), encoding="utf-8")

    print("## would create (deterministic)")
    for x in create_lines:
        print(x)
    if overflow:
        print(f"... {overflow} more (raise --max)")
    if skip_lines:
        print("\n## skipped (exists)")
        for x in skip_lines:
            print(x)
    if args.write and count > 0:
        sync_after("ingest", "knowledge", f"{count} docs")

    print("\n## agent worklist (needs judgment)")
    for x in _worklist(src):
        print(x)

    if warnings:
        print("\n## warnings")
        for w in warnings:
            print(w)
    return 0
