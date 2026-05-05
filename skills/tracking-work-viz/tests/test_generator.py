import json
from pathlib import Path
from work_viz.generator import generate_one_shot


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
