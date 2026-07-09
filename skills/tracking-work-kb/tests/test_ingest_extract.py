import sys, base64
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(LIB))
FIX = Path(__file__).resolve().parent / "fixtures" / "ingest-repo"

import ingest_extract as ie


def _by_slug(recs):
    return {r["slug"]: r for r in recs}


def test_openapi_operation_and_schema_records():
    import yaml
    data = yaml.safe_load((FIX / "openapi.yaml").read_text())
    recs = ie.extract_openapi(str(FIX / "openapi.yaml"), data)
    by = _by_slug(recs)
    # one operation
    assert "op-get-users" in by
    assert by["op-get-users"]["type"] == "API"
    assert by["op-get-users"]["title"] == "GET /users"
    assert by["op-get-users"]["description"] == "List users"
    # operation links to the User schema it $refs
    assert "schema-user" in by["op-get-users"]["links"]
    # two schemas
    assert by["schema-user"]["type"] == "Reference"
    assert "schema-account" in by["schema-user"]["links"]


def test_slugify():
    assert ie.slugify("GET /Users/{id}") == "get-users-id"
    assert ie.slugify("Account") == "account"


def test_sql_table_records():
    text = (FIX / "schema.sql").read_text()
    recs = ie.extract_sql(str(FIX / "schema.sql"), text)
    by = _by_slug(recs)
    assert set(by) == {"table-accounts", "table-orders"}
    assert by["table-accounts"]["type"] == "Reference"
    # columns preserved verbatim (types with parens survive)
    body = by["table-accounts"]["body"]
    assert "`balance`" in body and "DECIMAL(10,2)" in body
    # FK becomes a link to the referenced table
    assert "table-accounts" in by["table-orders"]["links"]


def test_sql_malformed_is_skipped():
    recs = ie.extract_sql("bad.sql", "CREATE TABLE oops (")
    assert recs == []


def test_sql_comment_dashes_inside_string_literal_preserved():
    # '--' inside a string default must not be treated as a comment.
    sql = "CREATE TABLE c (id INTEGER, note TEXT DEFAULT 'a--b', tail INTEGER);"
    recs = ie.extract_sql("c.sql", sql)
    assert len(recs) == 1
    body = recs[0]["body"]
    assert "`id`" in body and "`note`" in body and "`tail`" in body


def test_sql_unbalanced_table_does_not_drop_later_tables():
    sql = ("CREATE TABLE good1 (id INTEGER);\n"
           "CREATE TABLE oops (id INTEGER;\n"
           "CREATE TABLE good2 (id INTEGER);\n")
    recs = ie.extract_sql("m.sql", sql)
    slugs = {r["slug"] for r in recs}
    assert "table-good1" in slugs and "table-good2" in slugs


def test_split_top_commas_ignores_parens_in_string_literal():
    parts = ie._split_top_commas("status TEXT CHECK (status IN ('a)b','c')), name TEXT")
    assert len(parts) == 2


def test_main_continues_past_a_malformed_file(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("openapi: 3.0.0\npaths: {}\ncomponents:\n  schemas:\n    W:\n      properties:\n        - id\n")
    good = tmp_path / "good.sql"
    good.write_text("CREATE TABLE t1 (id INTEGER);\n")
    rc = ie.main([str(bad), str(good)])
    out = capsys.readouterr()
    assert rc == 0
    assert "table-t1" in out.out          # good file still extracted
    assert "warn" in out.err               # bad file reported, not silent


def test_json_openapi_parses_without_yaml(tmp_path):
    j = tmp_path / "openapi.json"
    j.write_text('{"openapi":"3.0.0","paths":{"/x":{"get":{"summary":"X"}}}}')
    recs = ie.detect_and_extract(str(j))
    assert any(r["slug"] == "op-get-x" for r in recs)
