"""cortex.cli delegates the `viz` group to cortex.viz.cli without touching its flags."""
from cortex import cli as cortex_cli


def test_viz_group_builds_site(workspaces_root, tmp_path):
    out = tmp_path / "out"
    rc = cortex_cli.main(["viz", "build", str(workspaces_root), "--out", str(out)])
    assert rc == 0
    assert (out / "index.html").is_file()
    assert (out / "workspaces" / "demo-ws" / "index.html").is_file()


def test_viz_unknown_subcommand_is_usage_error(capsys):
    rc = cortex_cli.main(["viz", "bogus-cmd"])
    assert rc == 2


def test_top_level_help_lists_viz(capsys):
    # viz is a registered group, so it shows in cortex's own help. main() catches
    # argparse's SystemExit(0) and returns it rather than propagating.
    rc = cortex_cli.main(["--help"])
    assert rc == 0
    assert "viz" in capsys.readouterr().out


def test_unknown_group_error_lists_viz(capsys):
    rc = cortex_cli.main(["bogus-group"])
    assert rc == 2
    assert "viz" in capsys.readouterr().err


def test_non_int_systemexit_is_normalized(monkeypatch, capsys):
    # A delegate that exits with a string code must not crash main(); mirror
    # CPython: print the message to stderr and return exit code 1.
    import cortex.viz.cli as vcli

    def _boom(argv):
        raise SystemExit("boom")

    monkeypatch.setattr(vcli, "main", _boom)
    rc = cortex_cli.main(["viz", "build"])
    assert rc == 1
    assert "boom" in capsys.readouterr().err
