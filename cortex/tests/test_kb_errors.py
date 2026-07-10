import io
import sys
from cortex import cli


def test_invalid_slug_exit_1(kbhome):
    assert cli.main(["kb", "new", "knowledge", "BAD_Slug", "--body", "x"]) == 1


def test_already_exists_exit_1(kbhome):
    assert cli.main(["kb", "new", "knowledge", "dup", "--body", "first"]) == 0
    assert cli.main(["kb", "new", "knowledge", "dup", "--body", "second"]) == 1


def test_no_active_no_workspace_exit_1(tmp_path, monkeypatch):
    (tmp_path / ".work/workspaces/ws-orphan/knowledge").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cli.main(["kb", "new", "knowledge", "foo", "--body", "x"]) == 1


def test_multiple_active_workspaces_exit_1(kbhome):
    wsb = kbhome / ".work/workspaces/ws-b/sessions/sess-b"
    wsb.mkdir(parents=True)
    (kbhome / ".work/workspaces/ws-b/.active.testid2").write_text("sess-b\n")
    assert cli.main(["kb", "new", "knowledge", "foo", "--body", "x"]) == 1


def test_author_human(kbhome):
    cli.main(["kb", "new", "knowledge", "human-entry", "--author", "human", "--body", "x"])
    assert "author: human" in (
        kbhome / ".work/workspaces/ws-a/knowledge/human-entry.md").read_text()


def test_body_from_stdin(kbhome, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("piped body"))
    cli.main(["kb", "new", "knowledge", "piped", "--body-from", "-"])
    assert "piped body" in (
        kbhome / ".work/workspaces/ws-a/knowledge/piped.md").read_text()


def test_explicit_workspace_override(kbhome):
    (kbhome / ".work/workspaces/ws-c/knowledge").mkdir(parents=True)
    cli.main(["kb", "new", "knowledge", "cross", "--workspace", "ws-c", "--body", "x"])
    assert (kbhome / ".work/workspaces/ws-c/knowledge/cross.md").is_file()


def test_open_defaults_author_human(kbhome, monkeypatch):
    monkeypatch.setenv("EDITOR", "true")
    rc = cli.main(["kb", "new", "knowledge", "editable", "--body", "x", "--open"])
    assert rc == 0
    assert "author: human" in (
        kbhome / ".work/workspaces/ws-a/knowledge/editable.md").read_text()


def test_workbench_session_flag(kbhome):
    (kbhome / ".work/workspaces/ws-a/sessions/sess-b/workbench").mkdir(parents=True)
    cli.main(["kb", "new", "workbench", "from-other", "--session", "sess-b", "--body", "x"])
    assert (kbhome / ".work/workspaces/ws-a/sessions/sess-b/workbench/from-other.md").is_file()


def test_workbench_no_active_no_session_exit_1(tmp_path, monkeypatch):
    (tmp_path / ".work/workspaces/ws-x/sessions/sess-x/workbench").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cli.main(["kb", "new", "workbench", "foo", "--workspace", "ws-x", "--body", "x"]) == 1


def test_bad_flag_exit_2(kbhome):
    assert cli.main(["kb", "new", "knowledge", "x", "--bogus"]) == 2


def test_body_from_missing_file_clean_error(kbhome, capsys):
    # Was: uncaught traceback. Now: clean CortexError -> exit 1.
    rc = cli.main(["kb", "new", "knowledge", "x", "--body-from", "/no/such/file"])
    assert rc == 1
    assert "Traceback" not in capsys.readouterr().err


def test_max_non_numeric_exit_1(kbhome):
    assert cli.main(["kb", "index", "--workspace", "ws-a", "--max", "abc"]) == 1


def test_dash_leading_flag_value_accepted(kbhome):
    rc = cli.main(["kb", "new", "knowledge", "changelog",
                   "--description", "-> migration notes", "--body", "b"])
    assert rc == 0
    assert "-> migration notes" in (
        kbhome / ".work/workspaces/ws-a/knowledge/changelog.md").read_text()


def test_open_missing_editor_clean_error(kbhome, monkeypatch, capsys):
    monkeypatch.setenv("EDITOR", "definitely-not-a-real-editor-xyz")
    rc = cli.main(["kb", "new", "knowledge", "ed", "--body", "x", "--open"])
    assert rc == 1
    assert "Traceback" not in capsys.readouterr().err
    assert (kbhome / ".work/workspaces/ws-a/knowledge/ed.md").is_file()  # written before open
