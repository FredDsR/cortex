from cortex import ingest as ie


def _by_slug(recs):
    return {r["slug"]: r for r in recs}


OPENAPI = """openapi: 3.0.0
info: {title: T, version: "1"}
paths:
  /users:
    get:
      summary: List users
      responses:
        "200":
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/User'
components:
  schemas:
    User:
      type: object
      properties:
        id: {type: integer}
        account: {$ref: '#/components/schemas/Account'}
    Account:
      type: object
      properties:
        name: {type: string}
"""


def test_openapi_operation_and_schema_records():
    import yaml
    recs = ie.extract_openapi("openapi.yaml", yaml.safe_load(OPENAPI))
    by = _by_slug(recs)
    assert by["op-get-users"]["type"] == "API"
    assert by["op-get-users"]["title"] == "GET /users"
    assert by["op-get-users"]["description"] == "List users"
    assert "schema-user" in by["op-get-users"]["links"]
    assert by["schema-user"]["type"] == "Reference"
    assert "schema-account" in by["schema-user"]["links"]


def test_slugify():
    assert ie.slugify("GET /Users/{id}") == "get-users-id"
    assert ie.slugify("Account") == "account"


def test_sql_tables_columns_and_fk_links():
    sql = ("CREATE TABLE accounts (id INTEGER PRIMARY KEY, balance DECIMAL(10,2));\n"
           "CREATE TABLE orders (id INTEGER, account_id INTEGER REFERENCES accounts(id));\n")
    by = _by_slug(ie.extract_sql("s.sql", sql))
    assert set(by) == {"table-accounts", "table-orders"}
    assert "DECIMAL(10,2)" in by["table-accounts"]["body"]
    assert "table-accounts" in by["table-orders"]["links"]


def test_sql_comment_dashes_inside_literal_preserved():
    recs = ie.extract_sql("c.sql", "CREATE TABLE c (id INTEGER, note TEXT DEFAULT 'a--b', tail INTEGER);")
    assert len(recs) == 1
    body = recs[0]["body"]
    assert "`id`" in body and "`note`" in body and "`tail`" in body


def test_sql_unbalanced_does_not_drop_later_tables():
    sql = "CREATE TABLE good1 (id INTEGER);\nCREATE TABLE oops (id INTEGER;\nCREATE TABLE good2 (id INTEGER);\n"
    warnings = []
    slugs = {r["slug"] for r in ie.extract_sql("m.sql", sql, warnings)}
    assert "table-good1" in slugs and "table-good2" in slugs
    assert any("unbalanced" in w for w in warnings)


def test_split_top_commas_ignores_parens_in_literal():
    parts = ie._split_top_commas("status TEXT CHECK (status IN ('a)b','c')), name TEXT")
    assert len(parts) == 2


def test_extract_all_continues_past_malformed_and_reports(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("openapi: 3.0.0\npaths: {}\ncomponents:\n  schemas:\n    W:\n      properties:\n        - id\n")
    good = tmp_path / "good.sql"
    good.write_text("CREATE TABLE t1 (id INTEGER);\n")
    records, warnings = ie.extract_all([str(bad), str(good)])
    assert any(r["slug"] == "table-t1" for r in records)   # good still extracted
    assert warnings                                        # bad reported, not silent


def test_json_openapi_parses_without_yaml(tmp_path):
    j = tmp_path / "openapi.json"
    j.write_text('{"openapi":"3.0.0","paths":{"/x":{"get":{"summary":"X"}}}}')
    recs = ie.detect_and_extract(str(j))
    assert any(r["slug"] == "op-get-x" for r in recs)


# ---- untrusted extracted text (issue #35) ----

BIDI = "\u202e"          # RLO
ZWSP = "\u200b"
BOM = "\ufeff"


def _no_invisibles(s):
    return not any(c in s for c in (BIDI, ZWSP, BOM))


def test_openapi_summary_description_is_sanitized():
    import yaml
    spec = yaml.safe_load(
        "openapi: 3.0.0\npaths:\n  /x:\n    get:\n"
        f'      summary: "List{ZWSP} {BIDI}users{BOM}"\n')
    rec = _by_slug(ie.extract_openapi("openapi.yaml", spec))["op-get-x"]
    assert rec["description"] == "List users"


def test_openapi_path_and_schema_names_are_sanitized():
    import yaml
    spec = yaml.safe_load(
        "openapi: 3.0.0\npaths:\n"
        f'  "/users{BIDI}":\n    get: {{summary: S}}\n'
        "components:\n  schemas:\n"
        f'    "User{ZWSP}":\n      properties:\n        "id{BOM}": {{type: integer}}\n')
    for rec in ie.extract_openapi("openapi.yaml", spec):
        assert _no_invisibles(rec["title"]), rec["slug"]
        assert _no_invisibles(rec["description"]), rec["slug"]
        assert _no_invisibles(rec["body"]), rec["slug"]


def test_sql_column_type_is_sanitized():
    # The column name is already fenced in by the `[\w.]+` name match; the
    # type is the rest of the definition, i.e. arbitrary text.
    sql = f"CREATE TABLE accounts (id DEC{ZWSP}IMAL{BIDI}(10,2){BOM});"
    rec = ie.extract_sql("s.sql", sql)[0]
    assert "`DECIMAL(10,2)`" in rec["body"]
    assert _no_invisibles(rec["body"])
