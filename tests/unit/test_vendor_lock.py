import hashlib
import json
from pathlib import Path

import cortex.viz

VIZ = Path(cortex.viz.__file__).parent
LOCK = VIZ / "vendor" / "vendor.lock.json"


def test_lockfile_exists_and_is_version_1():
    data = json.loads(LOCK.read_text())
    assert data["version"] == 1
    assert len(data["files"]) == 3


def test_every_vendored_file_matches_its_recorded_hash():
    data = json.loads(LOCK.read_text())
    for entry in data["files"]:
        blob = (VIZ / "vendor" / entry["name"]).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == entry["sha256"], entry["name"]
        assert len(blob) == entry["bytes"], entry["name"]


def test_first_party_assets_are_not_in_vendor():
    """app.js and app.css are ours. They must not sit among third-party files."""
    assert not (VIZ / "vendor" / "app.js").exists()
    assert not (VIZ / "vendor" / "app.css").exists()
    assert (VIZ / "assets" / "app.js").is_file()
    assert (VIZ / "assets" / "app.css").is_file()
    assert (VIZ / "assets" / "shell.html").is_file()


def test_every_lock_entry_records_provenance():
    data = json.loads(LOCK.read_text())
    for entry in data["files"]:
        assert entry["url"].startswith("https://")
        assert entry["version"]


def test_lock_covers_exactly_the_vendored_files():
    """A file added to vendor/ without a lock entry would ship unverified."""
    data = json.loads(LOCK.read_text())
    listed = {e["name"] for e in data["files"]}
    present = {p.name for p in (VIZ / "vendor").iterdir()
               if p.name != "vendor.lock.json"}
    assert present == listed
