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
