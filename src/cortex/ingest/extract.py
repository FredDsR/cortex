"""The deterministic half of `cortex kb ingest`: OpenAPI and SQL DDL to
concept dicts.

Deterministic because the failure mode of LLM ingestion is a plausible field
name that does not exist. Nothing here prints or writes; a caller passes paths
in and gets records plus a warnings list back, so one unparseable file never
aborts a run.

Every extracted string routes through `_oneline` / `_name`, since all of it
comes from a file cortex did not author and lands in `title:` / `description:`,
which reach the injection block a fresh agent gets at SessionStart. See
cortex/sanitize.py.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

from cortex.sanitize import sanitize


try:
    import yaml  # noqa
    _HAVE_YAML = True
except Exception:
    _HAVE_YAML = False

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


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
    """Collapse S to a single trimmed line. Sanitizes first: every string that
    reaches a knowledge doc comes from a file cortex did not author, and
    `\\s+` matches none of the invisible or bidi-control characters that would
    then ride `description:` into the injection block. See cortex/sanitize.py."""
    return re.sub(r"\s+", " ", sanitize(s)).strip()


def _name(s: str) -> str:
    """An extracted identifier, for display in `title:`/`description:`.

    Sanitizing can empty a name outright, since an identifier built only out of
    zero-width characters is nothing once they are gone. An emptied name is
    worse than it looks: `emit()` drops a falsy `title:` entirely and leaves a
    bare `description: "Schema "`, so the doc reaches the index block with no
    identity at all. slugify() already answers this case with an `x` fallback,
    so reuse it and the displayed name cannot disagree with the slug."""
    return _oneline(s) or slugify(s)


def _type_str(pdef, links):
    if not isinstance(pdef, dict):
        return "any"
    ref = pdef.get("$ref")
    if isinstance(ref, str):
        name = ref.split("/")[-1]
        links.append(f"schema-{slugify(name)}")
        return _oneline(name)
    t = pdef.get("type", "any")
    if t == "array":
        return f"array of {_type_str(pdef.get('items', {}), links)}"
    return _oneline(t)


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
        clean = _name(name)
        lines = [f"# {clean}", "", "Schema.", ""]
        for pname, pdef in props.items():
            lines.append(f"- `{_oneline(pname)}`: {_type_str(pdef, links)}")
        recs.append(dict(slug=f"schema-{slugify(name)}", type="Reference",
                         title=clean, description=f"Schema {clean}",
                         links=_dedupe(links), body="\n".join(lines), source=path))
    for p, item in (data.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(op, dict):
                continue
            title = f"{method.upper()} {_name(p)}"
            # Each candidate is sanitized before its truthiness decides the
            # fallback. Testing the raw value first lets a summary built only
            # out of zero-width characters win the `or` chain and then collapse
            # to "", which drops `description:` from the doc altogether. The
            # `or ""` guards are load-bearing: sanitize() stringifies, so a
            # missing key would otherwise sanitize to the literal "None".
            desc = (_oneline(op.get("summary") or "")
                    or _oneline(op.get("description") or "")
                    or title)
            links = []
            _collect_refs(op, links)
            body = f"# {title}\n\n{sanitize(op.get('summary', ''))}".rstrip()
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
        cname = _oneline(toks[0].strip('`"[]'))
        ctype = _oneline(toks[1]) if len(toks) > 1 else ""
        cols.append((cname, ctype))
    clean = _name(name)
    lines = [f"# {clean}", "", "| column | type |", "|--------|------|"]
    for c, t in cols:
        lines.append(f"| `{c}` | `{t}` |")
    return dict(slug=f"table-{slugify(name)}", type="Reference", title=clean,
                description=f"Table {clean} ({len(cols)} columns)",
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
        text = Path(path).read_text(encoding="utf-8", errors="replace")
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
