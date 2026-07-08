"""Localhost live-edit HTTP server. Serves built files for GET and a small
JSON API for reading/writing source. Enabled by `work-viz serve --edit`.

Editing never exists in a static build; this server is the only place the
write API lives, and it binds localhost only."""
from __future__ import annotations
import functools
import http.server
import json
import os
import secrets
import socketserver
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .parser import parse_world
from .generator import build, build_payload
from . import edit_backend


class EditHandler(http.server.SimpleHTTPRequestHandler):
    server_version = "work-viz-edit/1"

    # Bound per-server by make_edit_server via a dynamic subclass:
    workspaces_root: Path = None
    out_dir: Path = None
    token: str = ""
    commit_on_save: bool = False

    def _json(self, status: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _parse_world(self):
        return parse_world(self.workspaces_root, include_archive=True)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/capabilities":
            return self._json(200, {"edit": True, "token": self.token})
        if parsed.path == "/api/source":
            return self._handle_source(parse_qs(parsed.query))
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != "/api/save":
            return self._json(404, {"error": "not found"})
        if self.headers.get("X-Work-Viz-Token") != self.token:
            return self._json(403, {"error": "bad token"})
        length = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"error": "bad json"})
        return self._handle_save(req)

    def _handle_source(self, qs: dict) -> None:
        ids = qs.get("id")
        if not ids:
            return self._json(400, {"error": "missing id"})
        cid = ids[0]
        world = self._parse_world()
        doc = world.docs.get(cid)
        if doc is None:
            return self._json(404, {"error": "unknown id"})
        if doc.id.kind not in edit_backend.EDITABLE_KINDS:
            return self._json(200, {"editable": False})
        try:
            path = edit_backend.source_path_for(world, cid, self.workspaces_root)
        except FileNotFoundError:
            return self._json(404, {"error": "no source file"})
        except PermissionError:
            return self._json(400, {"error": "not editable"})
        return self._json(200, {
            "editable": True,
            "content": path.read_text(encoding="utf-8"),
            "hash": edit_backend.file_hash(path),
        })

    def _handle_save(self, req: dict):
        cid = req.get("id")
        content = req.get("content")
        base_hash = req.get("baseHash")
        scope = req.get("scope") or "root"
        scope_id = req.get("scopeId") or "/"
        if not cid or content is None or base_hash is None:
            return self._json(400, {"error": "missing fields"})
        world = self._parse_world()
        try:
            path = edit_backend.source_path_for(world, cid, self.workspaces_root)
        except LookupError:
            return self._json(404, {"error": "unknown id"})
        except PermissionError:
            return self._json(400, {"error": "not editable"})
        except FileNotFoundError:
            return self._json(404, {"error": "no source file"})
        current = edit_backend.file_hash(path)
        if current != base_hash:
            return self._json(409, {
                "currentContent": path.read_text(encoding="utf-8"),
                "currentHash": current,
            })
        self._atomic_write(path, content)
        self._commit(cid)
        world2 = self._parse_world()
        build(world2, self.out_dir, workspaces_root=self.workspaces_root)
        payload = build_payload(world2, scope, scope_id)
        return self._json(200, {
            "payload": payload,
            "content": content,
            "hash": edit_backend.file_hash(path),
        })

    def _atomic_write(self, path: Path, content: str) -> None:
        d = str(path.parent)
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, str(path))
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _commit(self, cid: str) -> None:
        if not self.commit_on_save:
            return
        script = os.path.expanduser(
            "~/.claude/skills/tracking-work-sync/scripts/commit_push.sh")
        if os.path.isfile(script) and os.access(script, os.X_OK):
            try:
                subprocess.run(["bash", script, f"track(viz): edit {cid}"],
                               check=False, capture_output=True, timeout=60)
            except Exception:
                pass

    def log_message(self, *args):  # quiet server
        pass


def make_edit_server(out_dir: Path, workspaces_root: Path, host: str, port: int,
                     commit_on_save: bool = False) -> socketserver.TCPServer:
    token = secrets.token_hex(16)
    # A per-server subclass carries the bound config, so concurrent servers
    # (e.g. in tests) never share state through the base class.
    bound = type("BoundEditHandler", (EditHandler,), {
        "workspaces_root": Path(workspaces_root),
        "out_dir": Path(out_dir),
        "token": token,
        "commit_on_save": commit_on_save,
    })
    handler = functools.partial(bound, directory=str(out_dir))
    httpd = socketserver.TCPServer((host, port), handler)
    httpd.token = token
    httpd.workspaces_root = Path(workspaces_root)
    return httpd
