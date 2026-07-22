import datetime
from cortex import cli

TODAY = datetime.date.today().isoformat()


def test_new_knowledge_happy_path(kbhome, capsys):
    rc = cli.main(["kb", "new", "knowledge", "sample", "--body", "hello world"])
    assert rc == 0
    path = kbhome / ".cortex/workspaces/ws-a/knowledge/sample.md"
    assert path.is_file()
    out = capsys.readouterr().out.strip()
    assert out == str(path)                       # prints the path
    text = path.read_text()
    assert "author: agent" in text
    assert f"created: {TODAY}" in text
    assert f"updated: {TODAY}" in text
    assert text.rstrip().endswith("hello world")


def test_new_workbench_uses_active_session(kbhome):
    rc = cli.main(["kb", "new", "workbench", "draft", "--body", "b"])
    assert rc == 0
    assert (kbhome / ".cortex/workspaces/ws-a/sessions/sess-a/workbench/draft.md").is_file()


def test_new_fields_written_in_canonical_order(kbhome):
    cli.main(["kb", "new", "knowledge", "decided",
              "--title", "A decision", "--type", "Decision",
              "--description", "why we chose X", "--body", "body text"])
    text = (kbhome / ".cortex/workspaces/ws-a/knowledge/decided.md").read_text()
    assert text == (
        "---\n"
        "title: A decision\n"
        "type: Decision\n"
        "author: agent\n"
        f"created: {TODAY}\n"
        f"updated: {TODAY}\n"
        "description: why we chose X\n"
        "---\n"
        "\n"
        "body text")


def test_new_plain_omits_optional_fields(kbhome):
    cli.main(["kb", "new", "knowledge", "plain", "--body", "hi"])
    text = (kbhome / ".cortex/workspaces/ws-a/knowledge/plain.md").read_text()
    assert "title:" not in text and "type:" not in text and "description:" not in text
    assert f"updated: {TODAY}" in text
