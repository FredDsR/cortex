"""Per-harness delivery: the stdout envelope and the hook wiring.

The only part of `inject` that knows a specific harness exists. Adding one is a
new `Adapter` subclass plus an entry in `ADAPTERS`, and touches nothing else.

Reads and writes a harness config file, so it does IO, but it prints nothing:
what the user is told about a wire or unwire is `cli.py`'s decision.
"""
from __future__ import annotations
import json
import shutil
from pathlib import Path

from cortex import atomic
from cortex.errors import CortexError

_CC_MATCHER = "startup|clear|compact"
_CC_MARK = "inject here --format=claude-code"

class Adapter:
    """Per-harness wiring + stdout envelope. Every adapter provides `format`;
    the config methods are filled in per harness."""
    name = ""

    def format(self, block: str) -> str:            # pragma: no cover - overridden
        raise NotImplementedError

    def wire(self, *, home: Path, project_path: Path | None = None) -> bool:      # pragma: no cover - overridden
        raise NotImplementedError

    def unwire(self, *, home: Path, project_path: Path | None = None) -> bool:    # pragma: no cover - overridden
        raise NotImplementedError

    def is_wired(self, *, home: Path, project_path: Path | None = None) -> bool:
        return False


class ClaudeCodeAdapter(Adapter):
    name = "claude-code"

    def format(self, block: str) -> str:
        payload = {"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": block,
        }}
        return json.dumps(payload)

    def _settings_path(self, home: Path, project_path: Path | None) -> Path:
        base = project_path if project_path is not None else home
        return Path(base) / ".claude" / "settings.json"

    def _cortex_command(self, home: Path) -> str:
        # The cortex bin lives under the store (<home>/.cortex/bin), not the
        # project, so the fallback is derived from the passed home.
        exe = shutil.which("cortex") or str(Path(home) / ".cortex" / "bin" / "cortex")
        return f"{exe} {_CC_MARK}"

    def _load(self, path: Path) -> dict:
        """Read and parse the settings file. A missing file is an empty config;
        an unreadable or malformed one raises rather than silently resolving to
        {} (which would let a write overwrite the user's whole settings.json)."""
        if not path.is_file():
            return {}
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            raise CortexError(f"cannot read {path}: {e}")
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            raise CortexError(
                f"{path} is not valid JSON; refusing to modify it. "
                "Fix the file or edit the SessionStart hook by hand.")
        if not isinstance(data, dict):
            raise CortexError(f"{path} is not a JSON object; refusing to modify it.")
        return data

    def _entries(self, data: dict) -> list:
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise CortexError("settings.json 'hooks' is not an object; refusing to modify it.")
        entries = hooks.setdefault("SessionStart", [])
        if not isinstance(entries, list):
            raise CortexError(
                "settings.json 'hooks.SessionStart' is not a list; refusing to modify it.")
        return entries

    def _is_ours(self, entry: dict) -> bool:
        return any(_CC_MARK in h.get("command", "")
                   for h in entry.get("hooks", []))

    def wire(self, *, home: Path, project_path: Path | None = None) -> bool:
        path = self._settings_path(home, project_path)
        data = self._load(path)
        entries = self._entries(data)
        if any(self._is_ours(e) for e in entries):
            return False
        entries.append({
            "matcher": _CC_MATCHER,
            "hooks": [{"type": "command", "command": self._cortex_command(home)}],
        })
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic.write_text(path, json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return True

    def unwire(self, *, home: Path, project_path: Path | None = None) -> bool:
        path = self._settings_path(home, project_path)
        if not path.is_file():
            return False
        data = self._load(path)
        entries = self._entries(data)
        kept = [e for e in entries if not self._is_ours(e)]
        if len(kept) == len(entries):
            return False
        data["hooks"]["SessionStart"] = kept
        atomic.write_text(path, json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return True

    def is_wired(self, *, home: Path, project_path: Path | None = None) -> bool:
        # A read-only query: degrade to "not wired" on an unreadable/malformed
        # file rather than raising, so `status` never crashes. Writes still refuse.
        try:
            data = self._load(self._settings_path(home, project_path))
        except CortexError:
            return False
        entries = data.get("hooks", {}).get("SessionStart", [])
        if not isinstance(entries, list):
            return False
        return any(self._is_ours(e) for e in entries)


ADAPTERS: dict[str, Adapter] = {a.name: a for a in (ClaudeCodeAdapter(),)}


def get_adapter(name: str) -> Adapter:
    try:
        return ADAPTERS[name]
    except KeyError:
        known = ", ".join(sorted(ADAPTERS)) or "(none)"
        raise CortexError(f"unknown harness '{name}'; known: {known}")
