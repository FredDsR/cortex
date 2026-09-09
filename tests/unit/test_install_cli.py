from cortex.install.cli import main, packaged_skills_dir


def test_packaged_skills_dir_finds_the_shipped_skills():
    path = packaged_skills_dir()
    assert path.name == "skills"
    assert (path / "cortex-tracking" / "SKILL.md").is_file()


def test_install_skills_verb_reports_and_exits_zero(tmp_path, monkeypatch,
                                                    capsys):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    rc = main(["install-skills"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "claude-code" in out
    assert (home / ".claude" / "skills" / "cortex-tracking").is_symlink()


def test_uninstall_skills_verb_removes_what_install_created(
        tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    main(["install-skills"])
    capsys.readouterr()
    rc = main(["uninstall-skills"])
    assert rc == 0
    assert "removed" in capsys.readouterr().out
    assert not (home / ".claude" / "skills" / "cortex-tracking").is_symlink()


def test_uninstall_dry_run_changes_nothing(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    main(["install-skills"])
    capsys.readouterr()
    main(["uninstall-skills", "--dry-run"])
    assert (home / ".claude" / "skills" / "cortex-tracking").is_symlink()


def _stub_run(calls):
    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0
        return Result()
    return fake_run


def test_upgrade_prefers_uv_when_available(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr("cortex.install.cli.shutil.which",
                        lambda n: "/usr/bin/uv" if n == "uv" else None)
    monkeypatch.setattr("cortex.install.cli.subprocess.run", _stub_run(calls))
    monkeypatch.setattr("cortex.install.cli.install_skills",
                        lambda **kw: ["ok"])
    assert main(["upgrade"]) == 0
    assert calls[0][:3] == ["uv", "tool", "install"]


def test_upgrade_falls_back_to_pip(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr("cortex.install.cli.shutil.which", lambda n: None)
    monkeypatch.setattr("cortex.install.cli.subprocess.run", _stub_run(calls))
    monkeypatch.setattr("cortex.install.cli.install_skills",
                        lambda **kw: ["ok"])
    assert main(["upgrade"]) == 0
    assert "pip" in calls[0]


def test_upgrade_pins_a_requested_version(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr("cortex.install.cli.shutil.which", lambda n: None)
    monkeypatch.setattr("cortex.install.cli.subprocess.run", _stub_run(calls))
    monkeypatch.setattr("cortex.install.cli.install_skills",
                        lambda **kw: ["ok"])
    main(["upgrade", "--to", "0.2.0"])
    assert any("cortex-tracking==0.2.0" in part for part in calls[0])


def test_upgrade_reports_a_failed_engine_upgrade(monkeypatch, capsys):
    def failing_run(cmd, **kwargs):
        class Result:
            returncode = 3
        return Result()

    monkeypatch.setattr("cortex.install.cli.shutil.which", lambda n: None)
    monkeypatch.setattr("cortex.install.cli.subprocess.run", failing_run)
    assert main(["upgrade"]) == 3
    assert "failed" in capsys.readouterr().err
