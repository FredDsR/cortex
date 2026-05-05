import json
import subprocess
import sys
from pathlib import Path


def test_cli_json_output(workspaces_root: Path, tmp_path: Path):
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
    assert payload["slug"] == "demo"
    assert any(s["slug"] == "feature-x" for s in payload["sessions"])
