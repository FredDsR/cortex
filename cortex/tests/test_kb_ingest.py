import pytest
from cortex import cli


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "src"
    r.mkdir()
    (r / "openapi.yaml").write_text(
        "openapi: 3.0.0\ninfo: {title: T, version: \"1\"}\npaths:\n"
        "  /users:\n    get:\n      summary: List users\n"
        "  /orders:\n    post:\n      summary: \"Create order: v2 # urgent\"\n")
    (r / "schema.sql").write_text(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY, name VARCHAR(255));\n"
        "CREATE TABLE orders (id INTEGER, account_id INTEGER REFERENCES accounts(id));\n")
    (r / "schema.prisma").write_text("model Widget {\n  id Int @id\n}\n")
    (r / "README.md").write_text("# Demo\n\n## API\n\nThe service exposes a REST API.\n")
    return r


def test_dry_run_plans_writes_nothing(kbhome, repo, capsys):
    assert cli.main(["kb", "ingest", "--from", str(repo), "--workspace", "ws-a"]) == 0
    out = capsys.readouterr().out
    assert "would create (deterministic)" in out
    assert "table-accounts [Reference]" in out
    assert "op-get-users [API]" in out
    assert "agent worklist" in out
    assert "schema.prisma" in out and "README.md" in out
    assert not (kbhome / ".work/workspaces/ws-a/knowledge/table-accounts.md").exists()


def test_only_sql_restricts(kbhome, repo, capsys):
    cli.main(["kb", "ingest", "--from", str(repo), "--workspace", "ws-a", "--only", "sql"])
    out = capsys.readouterr().out
    assert "table-accounts" in out and "op-get-users" not in out


def test_write_creates_docs_crosslinks_and_skips(kbhome, repo, capsys):
    assert cli.main(["kb", "ingest", "--from", str(repo), "--workspace", "ws-a", "--write"]) == 0
    kd = kbhome / ".work/workspaces/ws-a/knowledge"
    acc = kd / "table-accounts.md"
    assert acc.is_file()
    assert "type: Reference" in acc.read_text() and "title: accounts" in acc.read_text()
    assert "[[knowledge/table-accounts]]" in (kd / "table-orders.md").read_text()
    # colon/# summary must be valid YAML frontmatter
    op = kd / "op-post-orders.md"
    import yaml
    fmp = yaml.safe_load(op.read_text().split("---", 2)[1])
    assert fmp["description"] == "Create order: v2 # urgent"
    # idempotent: second write skips
    again = capsys.readouterr()  # drain
    cli.main(["kb", "ingest", "--from", str(repo), "--workspace", "ws-a", "--write"])
    assert "skipped (exists)" in capsys.readouterr().out


def test_max_caps_writes(kbhome, repo, capsys):
    cli.main(["kb", "ingest", "--from", str(repo), "--workspace", "ws-a", "--write", "--max", "1"])
    out = capsys.readouterr().out
    assert "more (raise --max)" in out
    n = len(list((kbhome / ".work/workspaces/ws-a/knowledge").glob("*.md")))
    assert n == 1


def test_only_empty_string_runs_full_ingest(kbhome, repo, capsys):
    assert cli.main(["kb", "ingest", "--from", str(repo), "--workspace", "ws-a", "--only", ""]) == 0
    out = capsys.readouterr().out
    assert "table-accounts" in out and "op-get-users" in out
