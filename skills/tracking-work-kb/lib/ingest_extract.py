#!/usr/bin/env python3
"""work-kb ingest extractor: OpenAPI + SQL DDL -> concept records.

Deterministic, dependency-light (stdlib json + PyYAML). Emits one record per
line to stdout, fields separated by US (\\x1f, unit separator):
slug US type US title US description US links US source US body_b64
US is used instead of TAB because bash `IFS=$'\t' read` treats TAB as
whitespace-IFS and collapses empty fields (e.g. an empty links column), which
would shift every later field. US is non-whitespace, so empty fields survive.
Warnings go to stderr; unparseable inputs are skipped, never fatal.
"""
from __future__ import annotations
import sys, re, base64, json

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
    """Remove -- line and /* */ block comments, respecting single-quoted string
    literals (SQL '' escaping) so a '--' or '/*' inside a literal is preserved."""
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
    """Split on top-level commas, ignoring commas inside parens or '..' literals."""
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
    """Return the index of the ')' matching the '(' at popen, respecting
    single-quoted literals, or -1 if unbalanced."""
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


def extract_sql(path, text):
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
            # Unbalanced: skip this statement but keep scanning for later ones.
            print(f"warn: unbalanced CREATE TABLE {name} in {path}, skipping", file=sys.stderr)
            idx = start
            continue
        recs.append(_table_concept(path, name, text[popen + 1:close]))
        idx = close + 1
    return recs


def detect_and_extract(path):
    ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        print(f"warn: cannot read {path}: {e}", file=sys.stderr)
        return []
    if ext == "sql":
        return extract_sql(path, text)
    if ext == "json":
        # OpenAPI/Swagger JSON parses with stdlib; no PyYAML needed.
        try:
            data = json.loads(text)
        except Exception as e:
            print(f"warn: cannot parse {path}: {e}", file=sys.stderr)
            return []
    elif not _HAVE_YAML:
        print(f"warn: PyYAML unavailable, skipping {path}", file=sys.stderr)
        return []
    else:
        try:
            data = yaml.safe_load(text)
        except Exception as e:
            print(f"warn: cannot parse {path}: {e}", file=sys.stderr)
            return []
    if isinstance(data, dict) and ("openapi" in data or "swagger" in data or "paths" in data):
        return extract_openapi(path, data)
    return []


_US = "\x1f"  # unit separator: field delimiter for the record wire format


def emit_record(rec, out):
    body_b64 = base64.b64encode(rec["body"].encode("utf-8")).decode("ascii")
    fields = [rec["slug"], rec["type"], _oneline(rec["title"]),
              _oneline(rec["description"]), ",".join(rec["links"]),
              rec["source"], body_b64]
    out.write(_US.join(fields) + "\n")


def main(argv):
    seen = set()
    for path in argv:
        # One malformed artifact must not abort extraction of the rest.
        try:
            recs = detect_and_extract(path)
        except Exception as e:
            print(f"warn: failed to extract {path}: {e}", file=sys.stderr)
            continue
        for rec in recs:
            if rec["slug"] in seen:
                print(f"warn: duplicate slug {rec['slug']} from {path}, skipping", file=sys.stderr)
                continue
            seen.add(rec["slug"])
            emit_record(rec, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
