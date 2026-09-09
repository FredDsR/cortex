"""Every place that states a version must state the same one.

Before packaging, plugin.json and marketplace.json both claimed 1.0.0 with no
tag or release behind either. release-please keeps all four in step; these
tests fail if a hand edit or a misconfigured extra-files entry lets them drift.
"""
import json
import re

import pytest

from cortex import __version__
from support import REPO_ROOT

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _json(rel):
    return json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))


def _pyproject_name():
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^name = "([^"]+)"', text, re.M).group(1)


def test_source_version_is_semver():
    assert SEMVER.match(__version__), __version__


@pytest.mark.parametrize("rel,path", [
    (".release-please-manifest.json", lambda d: d["."]),
    (".claude-plugin/plugin.json", lambda d: d["version"]),
    (".claude-plugin/marketplace.json", lambda d: d["plugins"][0]["version"]),
])
def test_declared_versions_match_the_source(rel, path):
    assert path(_json(rel)) == __version__, rel


def test_release_please_targets_the_distribution_name():
    """A mismatch here silently stops the release PR touching pyproject."""
    cfg = _json("release-please-config.json")
    assert cfg["packages"]["."]["package-name"] == _pyproject_name()


def test_release_please_updates_both_plugin_manifests():
    """These two are the files that previously drifted, so the extra-files
    entries that keep them in step are worth asserting."""
    cfg = _json("release-please-config.json")
    entries = cfg["packages"]["."]["extra-files"]
    json_targets = {e["path"] for e in entries
                    if isinstance(e, dict) and e.get("type") == "json"}
    assert json_targets == {
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
    }


def test_distribution_name_is_not_the_taken_pypi_name():
    """`cortex` and `cortex-cli` are taken on PyPI. The import package and the
    console script stay `cortex`; only the distribution differs."""
    assert _pyproject_name() not in ("cortex", "cortex-cli")


def test_version_line_carries_the_release_please_annotation():
    """release-please derives the __init__.py path from the DISTRIBUTION name,
    so for `agentic-cortex` it looks for src/agentic_cortex/__init__.py and
    never finds ours. The generic updater targets the real path, and it only
    acts on an annotated line. Without both, tags advance while the published
    version stays put.
    """
    src = (REPO_ROOT / "src" / "cortex" / "__init__.py").read_text()
    version_line = next(
        line for line in src.splitlines()
        if line.startswith("__version__")
    )
    assert "x-release-please-version" in version_line


def test_release_please_updates_the_version_file_via_the_generic_updater():
    cfg = _json("release-please-config.json")
    entries = cfg["packages"]["."]["extra-files"]
    generic = [e for e in entries
               if isinstance(e, dict) and e.get("type") == "generic"]
    assert {e["path"] for e in generic} == {"src/cortex/__init__.py"}


def test_pyproject_version_is_dynamic():
    """hatchling reads __init__.py, which is why the generic updater above is
    the only thing that moves the version. release-please skips a dynamic
    pyproject, and that is correct rather than a gap."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in text
    assert 'path = "src/cortex/__init__.py"' in text


def test_release_tags_are_not_component_prefixed():
    """include-component-in-tag defaults to true, which tags a single-package
    repo as agentic-cortex-v0.2.0 rather than v0.2.0. The docs and the
    `cortex upgrade --to` examples assume the plain form, and tag format is
    painful to change once tags exist."""
    cfg = _json("release-please-config.json")
    assert cfg["include-component-in-tag"] is False
