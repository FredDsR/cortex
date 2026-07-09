#!/usr/bin/env python3
"""work-kb ingest extractor: OpenAPI + SQL DDL -> TSV concept records.

Deterministic, dependency-light (stdlib json + PyYAML). Emits one record per
line to stdout: slug\ttype\ttitle\tdescription\tlinks\tsource\tbody_b64
Warnings go to stderr; unparseable inputs are skipped, never fatal.
"""
from __future__ import annotations
import sys, re, base64

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


def _split_top_commas(s):
    parts, depth, cur = [], 0, ""
    for c in s:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == "," and depth == 0:
            parts.append(cur); cur = ""
        else:
            cur += c
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


def extract_sql(path, text):
    text = re.sub(r"--[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
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
        depth, i, matched = 0, popen, False
        while i < len(text):
            c = text[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    matched = True
                    break
            i += 1
        if not matched:
            print(f"warn: unbalanced CREATE TABLE {name} in {path}, skipping", file=sys.stderr)
            break
        recs.append(_table_concept(path, name, text[popen + 1:i]))
        idx = i + 1
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
    if not _HAVE_YAML:
        print(f"warn: PyYAML unavailable, skipping {path}", file=sys.stderr)
        return []
    try:
        data = yaml.safe_load(text)
    except Exception as e:
        print(f"warn: cannot parse {path}: {e}", file=sys.stderr)
        return []
    if isinstance(data, dict) and ("openapi" in data or "swagger" in data or "paths" in data):
        return extract_openapi(path, data)
    return []


def emit_record(rec, out):
    body_b64 = base64.b64encode(rec["body"].encode("utf-8")).decode("ascii")
    fields = [rec["slug"], rec["type"], _oneline(rec["title"]),
              _oneline(rec["description"]), ",".join(rec["links"]),
              rec["source"], body_b64]
    out.write("\t".join(fields) + "\n")


def main(argv):
    seen = set()
    for path in argv:
        for rec in detect_and_extract(path):
            if rec["slug"] in seen:
                print(f"warn: duplicate slug {rec['slug']} from {path}, skipping", file=sys.stderr)
                continue
            seen.add(rec["slug"])
            emit_record(rec, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
