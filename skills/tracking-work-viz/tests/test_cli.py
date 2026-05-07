import json
import subprocess
import sys
from pathlib import Path


def test_cli_json_output(workspaces_root: Path, tmp_path: Path):
    """--json now emits the full World (top-level workspaces/edges/ghosts keys)."""
    repo_root = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable, "-c",
        "import sys; sys.path.insert(0, %r); "
        "from work_viz.cli import main; "
        "sys.exit(main(['--workspaces-root', %r, 'demo', '--json']))" % (
            str(repo_root), str(workspaces_root),
        ),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    payload = json.loads(r.stdout)
    # World shape: top-level keys are workspaces, edges, ghosts
    assert "workspaces" in payload
    assert "edges" in payload
    assert "ghosts" in payload
    # The demo workspace must be present
    demo_ws = next((w for w in payload["workspaces"] if w["slug"] == "demo"), None)
    assert demo_ws is not None, f"demo not found in workspaces: {[w['slug'] for w in payload['workspaces']]}"
    assert any(s["slug"] == "feature-x" for s in demo_ws["sessions"])
