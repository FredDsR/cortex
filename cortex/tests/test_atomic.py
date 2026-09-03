"""Tests for cortex.atomic: the single crash-safe write in the store.

Every write under cortex/ goes through this so an interrupted run cannot
leave a truncated file behind for `sync_after()` to commit and push, or for
the harness to parse at startup.
"""
import json
import os
import tempfile

import pytest

from cortex import atomic


def _tmp_leftovers(d):
    return [p.name for p in d.iterdir() if ".tmp" in p.name]


def test_write_text_creates_the_file(tmp_path):
    target = tmp_path / "new.md"
    atomic.write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_write_text_overwrites_existing_content(tmp_path):
    target = tmp_path / "doc.md"
    target.write_text("old\n", encoding="utf-8")
    atomic.write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"


def test_write_text_accepts_a_str_path(tmp_path):
    target = tmp_path / "doc.md"
    atomic.write_text(str(target), "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_write_text_honours_the_encoding(tmp_path):
    target = tmp_path / "doc.md"
    atomic.write_text(target, "café\n", encoding="latin-1")
    assert target.read_bytes() == b"caf\xe9\n"


def test_write_text_leaves_no_temp_file_behind(tmp_path):
    atomic.write_text(tmp_path / "doc.md", "hello\n")
    assert _tmp_leftovers(tmp_path) == []


def test_temp_file_is_created_beside_the_target(tmp_path, monkeypatch):
    """Same directory means same filesystem, which is what makes os.replace
    atomic. A temp under /tmp would degrade to a copy across devices."""
    seen = {}
    real_mkstemp = tempfile.mkstemp

    def spy(*a, **kw):
        seen["dir"] = kw.get("dir")
        return real_mkstemp(*a, **kw)

    monkeypatch.setattr(atomic.tempfile, "mkstemp", spy)
    target = tmp_path / "sub" / "doc.md"
    target.parent.mkdir()
    atomic.write_text(target, "hello\n")
    assert seen["dir"] == str(target.parent)


def test_data_is_fsynced_before_the_rename(tmp_path, monkeypatch):
    """Without the fsync the rename can land before the bytes do, so a power
    loss leaves an empty file where the old one used to be."""
    order = []
    real_fsync, real_replace = os.fsync, os.replace
    monkeypatch.setattr(atomic.os, "fsync", lambda fd: (order.append("fsync"), real_fsync(fd))[1])
    monkeypatch.setattr(atomic.os, "replace",
                        lambda s, d: (order.append("replace"), real_replace(s, d))[1])
    atomic.write_text(tmp_path / "doc.md", "hello\n")
    assert order.index("fsync") < order.index("replace")


def test_the_directory_entry_is_fsynced_after_the_rename(tmp_path, monkeypatch):
    """fsyncing the file only makes its contents durable. The rename itself
    lives in the parent directory and needs its own flush."""
    synced = []
    real_fsync = os.fsync

    def spy(fd):
        synced.append(os.fstat(fd).st_mode)
        return real_fsync(fd)

    monkeypatch.setattr(atomic.os, "fsync", spy)
    atomic.write_text(tmp_path / "doc.md", "hello\n")
    import stat
    assert any(stat.S_ISDIR(m) for m in synced), "parent directory was not fsynced"


def test_a_new_file_gets_ordinary_permissions(tmp_path):
    """mkstemp hands back 0600; docs in the store must not silently become
    owner-only just because the write went through a temp file."""
    target = tmp_path / "doc.md"
    atomic.write_text(target, "hello\n")
    expected = 0o666 & ~_umask()
    assert target.stat().st_mode & 0o777 == expected


def test_an_existing_file_keeps_its_permissions(tmp_path):
    target = tmp_path / "doc.md"
    target.write_text("old\n", encoding="utf-8")
    os.chmod(target, 0o640)
    atomic.write_text(target, "new\n")
    assert target.stat().st_mode & 0o777 == 0o640


def _umask():
    cur = os.umask(0o022)
    os.umask(cur)
    return cur


def test_a_refused_directory_fsync_does_not_fail_the_write(tmp_path, monkeypatch):
    """Once os.replace returns, the new content is already live. A directory
    fsync the filesystem refuses (CIFS answers EINVAL) is a durability
    shortfall, not a failed write, and must not be raised at the caller:
    cli.py only catches CortexError, so kb would skip print(path) and
    sync_after() over a write that actually landed."""
    import stat as _stat
    real_fsync = os.fsync

    def refuse_dirs(fd):
        if _stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(22, "Invalid argument")
        return real_fsync(fd)

    monkeypatch.setattr(atomic.os, "fsync", refuse_dirs)
    target = tmp_path / "doc.md"
    atomic.write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"
    assert _tmp_leftovers(tmp_path) == []


def test_a_long_target_name_still_writes(tmp_path):
    """The temp name carries the target's name plus mkstemp's suffix, so a
    long-but-legal filename must not push it past the 255-byte limit.
    `kb new --slug` imposes no length cap."""
    target = tmp_path / ("a" * 250 + ".md")
    atomic.write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_regenerable_output_can_skip_the_fsyncs(tmp_path):
    """`durable=False` keeps the atomic replace but drops the two fsyncs, for
    output that is rebuilt from source rather than being the source."""
    calls = []
    real_fsync = os.fsync
    target = tmp_path / "doc.md"
    target.write_text("old\n", encoding="utf-8")
    import unittest.mock as mock
    with mock.patch.object(atomic.os, "fsync", lambda fd: calls.append(fd)):
        with open(target, encoding="utf-8") as held:
            atomic.write_text(target, "new\n", durable=False)
            assert held.read() == "old\n", "replace must still be atomic"
    assert calls == []
    assert target.read_text(encoding="utf-8") == "new\n"
    assert real_fsync is os.fsync


def test_viz_build_does_not_fsync_regenerable_output(workspaces_root, tmp_path, monkeypatch):
    """`viz serve --edit` rebuilds every page on every save, so fsyncing each
    one would cost two syncs per output file per keystroke-save."""
    from cortex.parser import parse_world
    from cortex.viz.generator import build
    calls = []
    monkeypatch.setattr(atomic.os, "fsync", lambda fd: calls.append(fd))
    build(parse_world(workspaces_root), tmp_path / "out", workspaces_root=workspaces_root)
    assert calls == []
    assert (tmp_path / "out" / "index.html").is_file()


def test_store_writes_are_still_fsynced(kbhome, monkeypatch):
    """The counterpart: a knowledge doc is source, so it keeps its fsyncs."""
    from cortex import kb
    calls = []
    real_fsync = os.fsync
    monkeypatch.setattr(atomic.os, "fsync", lambda fd: (calls.append(fd), real_fsync(fd))[1])
    kb.cmd_new(_kb_new_args(workspace="ws-a", slug="probe"))
    assert len(calls) >= 2, "expected the file and its directory to be fsynced"


def test_the_sync_gitignore_excludes_orphaned_temp_files():
    """`except BaseException` cleans up after Ctrl-C, but not after SIGKILL or
    power loss. sync.push runs `git add -A .`, which would otherwise commit an
    orphaned temp file and push it to every device."""
    import pathlib as _pl
    tpl = _pl.Path(__file__).resolve().parents[2] / "skills" / "cortex-sync" / "templates" / "gitignore"
    assert "*.tmp" in tpl.read_text(encoding="utf-8").split()


def test_a_failed_write_leaves_the_original_intact(tmp_path, monkeypatch):
    target = tmp_path / "doc.md"
    target.write_text("old\n", encoding="utf-8")

    def boom(src, dst):
        raise KeyboardInterrupt

    monkeypatch.setattr(atomic.os, "replace", boom)
    with pytest.raises(KeyboardInterrupt):
        atomic.write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "old\n"


def test_a_failed_write_leaves_no_temp_file_behind(tmp_path, monkeypatch):
    target = tmp_path / "doc.md"
    target.write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(atomic.os, "replace",
                        lambda s, d: (_ for _ in ()).throw(OSError("nope")))
    with pytest.raises(OSError):
        atomic.write_text(target, "new\n")
    assert _tmp_leftovers(tmp_path) == []


def test_a_failed_write_does_not_create_a_missing_target(tmp_path, monkeypatch):
    target = tmp_path / "doc.md"
    monkeypatch.setattr(atomic.os, "replace",
                        lambda s, d: (_ for _ in ()).throw(OSError("nope")))
    with pytest.raises(OSError):
        atomic.write_text(target, "new\n")
    assert not target.exists()


def test_writing_through_a_symlink_keeps_the_symlink(tmp_path):
    """os.replace clobbers a symlink rather than following it. A dotfiles-managed
    ~/.claude/settings.json must stay a link to the repo, not become a copy."""
    real = tmp_path / "dotfiles" / "settings.json"
    real.parent.mkdir()
    real.write_text("old\n", encoding="utf-8")
    link = tmp_path / "settings.json"
    link.symlink_to(real)

    atomic.write_text(link, "new\n")

    assert link.is_symlink(), "the symlink was replaced by a regular file"
    assert real.read_text(encoding="utf-8") == "new\n"
    assert _tmp_leftovers(real.parent) == []


def test_write_text_replaces_rather_than_truncating_in_place(tmp_path):
    """A reader holding the old file keeps seeing the old bytes, which is the
    observable difference between os.replace and an in-place rewrite."""
    target = tmp_path / "doc.md"
    target.write_text("old\n", encoding="utf-8")
    with open(target, encoding="utf-8") as held:
        atomic.write_text(target, "new\n")
        assert held.read() == "old\n"
    assert target.read_text(encoding="utf-8") == "new\n"


# --- call sites -------------------------------------------------------------

def test_no_bare_file_write_remains_in_the_package():
    """Guard: a new bare `write_text`/`write_bytes` reintroduces the torn-write
    bug. Walks the AST rather than grepping, so documenting the anti-pattern in
    a comment or docstring does not trip it."""
    import ast
    import pathlib
    pkg = pathlib.Path(atomic.__file__).parent
    banned = {"write_text", "write_bytes"}
    offenders = []
    for py in sorted(pkg.rglob("*.py")):
        rel = py.relative_to(pkg)
        if rel.parts[0] == "tests" or rel.name in ("conftest.py", "atomic.py"):
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not isinstance(fn, ast.Attribute) or fn.attr not in banned:
                continue
            if isinstance(fn.value, ast.Name) and fn.value.id == "atomic":
                continue
            offenders.append(f"{rel}:{fn.lineno} {fn.attr}")
    assert offenders == []


def test_kb_new_does_not_leave_a_partial_doc(kbhome, monkeypatch):
    """kb writes are followed by sync_after(), which commits and pushes, so a
    torn doc here propagates to every other device."""
    from cortex import kb
    monkeypatch.setattr(atomic.os, "replace",
                        lambda s, d: (_ for _ in ()).throw(KeyboardInterrupt))
    args = _kb_new_args(workspace="ws-a", slug="probe")
    with pytest.raises(KeyboardInterrupt):
        kb.cmd_new(args)
    kdir = kbhome / ".cortex" / "workspaces" / "ws-a" / "knowledge"
    assert not (kdir / "probe.md").exists()
    assert _tmp_leftovers(kdir) == []


def test_kb_index_does_not_leave_a_partial_index(kbhome, monkeypatch):
    from cortex import kb
    kb.cmd_new(_kb_new_args(workspace="ws-a", slug="probe"))
    kdir = kbhome / ".cortex" / "workspaces" / "ws-a" / "knowledge"
    kb.cmd_index(_kb_index_args(workspace="ws-a"))
    before = (kdir / "INDEX.md").read_text(encoding="utf-8")

    monkeypatch.setattr(atomic.os, "replace",
                        lambda s, d: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        kb.cmd_index(_kb_index_args(workspace="ws-a"))
    assert (kdir / "INDEX.md").read_text(encoding="utf-8") == before
    assert _tmp_leftovers(kdir) == []


def test_inject_wire_does_not_corrupt_settings_json(tmp_path, monkeypatch):
    """A torn ~/.claude/settings.json breaks every session on the machine,
    including ones that never touch cortex."""
    from cortex import inject
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    original = {"model": "opus", "hooks": {"SessionStart": []}}
    settings.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")

    monkeypatch.setattr(atomic.os, "replace",
                        lambda s, d: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        inject.get_adapter("claude-code").wire(home=tmp_path)
    assert json.loads(settings.read_text(encoding="utf-8")) == original
    assert _tmp_leftovers(settings.parent) == []


class _Args:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _kb_new_args(**over):
    base = dict(kind="knowledge", slug="probe", workspace=None, session=None,
                title="Probe", type="Gotcha", description="a probe",
                author=None, body="hello", body_file=None, open=False)
    base.update(over)
    return _Args(**base)


def _kb_index_args(**over):
    base = dict(workspace=None, max="20", write=True)
    base.update(over)
    return _Args(**base)
