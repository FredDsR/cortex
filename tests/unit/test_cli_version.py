from cortex import __version__
from cortex.cli import main, resolve_version


def test_resolve_version_returns_a_string():
    assert isinstance(resolve_version(), str)
    assert resolve_version()


def test_resolve_version_falls_back_to_dunder_when_not_installed(monkeypatch):
    def boom(name):
        from importlib.metadata import PackageNotFoundError
        raise PackageNotFoundError(name)

    monkeypatch.setattr("cortex.cli.metadata_version", boom)
    assert resolve_version() == __version__


def test_version_subcommand_prints_version(capsys):
    rc = main(["version"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == resolve_version()
