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
