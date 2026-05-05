import json
from pathlib import Path
from work_viz.generator import generate_one_shot
from work_viz.generator import generate_dashboard


def test_one_shot_writes_self_contained_html(workspaces_root: Path, tmp_path: Path):
    out = generate_one_shot(workspaces_root, "demo", out_dir=tmp_path)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    # MODE marker is replaced
    assert "@@MODE@@" not in text
    assert '"static"' in text
    # DATA placeholder is replaced with valid JSON
    assert "@@DATA@@" not in text
    # The slug should appear in the embedded data
    assert '"slug": "demo"' in text or '"slug":"demo"' in text
    # Vendor links should be relative
    assert 'src="vendor/cytoscape.min.js"' in text


def test_dashboard_lists_workspaces(workspaces_root: Path, tmp_path: Path):
    out = generate_dashboard(workspaces_root, out_dir=tmp_path)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "@@DATA@@" not in text
    assert '"slug": "demo"' in text or '"slug":"demo"' in text


def test_script_tag_injection_neutralized(workspaces_root: Path, tmp_path: Path):
    """A task body containing </script> must not break out of the inline <script> block."""
    # Inject a malicious task body into a writable copy of the fixture
    import shutil
    dest = tmp_path / "ws"
    shutil.copytree(workspaces_root, dest)
    task_path = dest / "demo" / "sessions" / "feature-x" / "tasks" / "task-foo.md"
    task_path.write_text(task_path.read_text() + "\n\n</script><script>window.PWNED=true</script>\n")
    from work_viz.generator import generate_one_shot
    out = generate_one_shot(dest, "demo", out_dir=tmp_path)
    text = out.read_text(encoding="utf-8")
    # The literal </script> in the body must be escaped in the inlined JSON.
    assert "</script><script>window.PWNED=true</script>" not in text
    # The escaped form should be present.
    assert "<\\/script>" in text or "<\\/" in text
