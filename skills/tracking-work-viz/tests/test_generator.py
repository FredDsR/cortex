"""Tests for the static-site generator."""
from pathlib import Path
import json
import pytest
from work_viz.parser import parse_world
from work_viz.generator import build


def test_build_creates_output_dir(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    assert out.is_dir()


def test_build_stages_vendor(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    assert (out / "vendor" / "cytoscape.min.js").is_file()
    assert (out / "vendor" / "marked.min.js").is_file()
    assert (out / "vendor" / "app.js").is_file()
    assert (out / "vendor" / "app.css").is_file()


def test_build_copies_task_md(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    assert (out / "workspaces/demo-ws/sessions/alpha/tasks/task-a.md").is_file()
    assert (out / "workspaces/demo-ws/sessions/alpha/SUMMARY.md").is_file()


def test_build_skips_ghosts(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    # The ghost memory/architecture reference must not produce a file.
    assert not (out / "workspaces/demo-ws/memory/architecture.md").exists()
