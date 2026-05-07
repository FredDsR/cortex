"""Watch-mode HTTP server with SSE change notifications. Stdlib only."""
from __future__ import annotations
import json
import os
import socket
import threading
import time
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue, Empty
from typing import Optional

from .parser import parse_world
from .generator import _TEMPLATES_DIR


def _scan_mtimes(root: Path) -> dict:
    out: dict = {}
    if not root.is_dir():
        return out
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            p = Path(dirpath) / fn
            try:
                out[str(p)] = p.stat().st_mtime
            except OSError:
                pass
    return out


def _pick_port(preferred_range=(8765, 8775)) -> int:
    for port in range(preferred_range[0], preferred_range[1] + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    # Fall back to OS-assigned
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _SSEHub:
    """Fan-out hub: one queue per connected SSE client."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: list = []

    def register(self) -> Queue:
        q: Queue = Queue()
        with self._lock:
            self._clients.append(q)
        return q

    def unregister(self, q: Queue) -> None:
        with self._lock:
            try:
                self._clients.remove(q)
            except ValueError:
                pass

    def broadcast(self, event: str) -> None:
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            q.put(event)


class VizServer:
    """Threading HTTP server that serves the viewer UI plus /data.json and /events."""

    def __init__(self, workspaces_root: Path, slug: str, port: int = 0,
                 runtime_dir: Optional[Path] = None) -> None:
        self.workspaces_root = workspaces_root
        self.slug = slug
        self.port = port or _pick_port()
        self.runtime_dir = runtime_dir or (Path.home() / ".work" / "viz")
        self._hub = _SSEHub()
        self._server: Optional[ThreadingHTTPServer] = None
        self._serve_thread: Optional[threading.Thread] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _build_handler(self):
        hub = self._hub
        slug = self.slug
        workspaces_root = self.workspaces_root
        runtime_dir = self.runtime_dir
        templates_dir = _TEMPLATES_DIR

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args, **_kwargs):
                return  # quiet

            def do_GET(self):
                if self.path == "/" or self.path == "/index.html":
                    raw = (templates_dir / "index.html").read_text(encoding="utf-8")
                    html = (raw
                            .replace('"@@MODE@@"', '"dynamic"')
                            .replace("@@DATA@@", "null")
                            .replace("@@CY_DATA@@", "null"))
                    self._send_text(html, "text/html; charset=utf-8")
                    return
                if self.path == "/data.json":
                    try:
                        world = parse_world(workspaces_root)
                        ws_obj = next(
                            (w for w in world.workspaces if w.slug == slug), None
                        )
                        if ws_obj is None:
                            body = json.dumps({"error": "workspace_not_found", "detail": f"workspace not found: {slug}"})
                            self.send_response(HTTPStatus.NOT_FOUND)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            data = body.encode("utf-8")
                            self.send_header("Content-Length", str(len(data)))
                            self.end_headers()
                            self.wfile.write(data)
                            return
                        data = asdict(ws_obj)
                        data["available_workspaces"] = [ws.slug for ws in world.workspaces]
                        body = json.dumps(data, ensure_ascii=False)
                    except Exception as exc:
                        body = json.dumps({"error": "parse_failed", "detail": str(exc)})
                        self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        data = body.encode("utf-8")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        return
                    self._send_text(body, "application/json; charset=utf-8")
                    return
                if self.path == "/events":
                    self._serve_sse(hub)
                    return
                if self.path.startswith("/vendor/"):
                    rel = self.path[len("/vendor/"):]
                    base = (runtime_dir / "vendor").resolve()
                    try:
                        fp = (base / rel).resolve()
                        fp.relative_to(base)
                    except (ValueError, OSError):
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
                    if fp.is_file():
                        ctype = "text/javascript" if fp.suffix == ".js" else "text/css"
                        self._send_bytes(fp.read_bytes(), ctype)
                        return
                self.send_error(HTTPStatus.NOT_FOUND)

            def _send_text(self, body: str, ctype: str):
                data = body.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _send_bytes(self, data: bytes, ctype: str):
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _serve_sse(self, hub: "_SSEHub"):
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                # Initial comment to flush headers
                try:
                    self.wfile.write(b": connected\n\n")
                    self.wfile.flush()
                except OSError:
                    return
                q = hub.register()
                try:
                    while True:
                        try:
                            event = q.get(timeout=15)
                            payload = f"event: change\ndata: {event}\n\n"
                            self.wfile.write(payload.encode("utf-8"))
                            self.wfile.flush()
                        except Empty:
                            try:
                                self.wfile.write(b": keepalive\n\n")
                                self.wfile.flush()
                            except OSError:
                                break
                        except OSError:
                            break
                finally:
                    hub.unregister(q)

        return Handler

    def _watch_loop(self):
        target = self.workspaces_root / self.slug
        prev = _scan_mtimes(target)
        debounce_until = 0.0
        while not self._stop_event.wait(1.0):
            now = _scan_mtimes(target)
            if now != prev:
                debounce_until = time.monotonic() + 0.25
                prev = now
            if debounce_until and time.monotonic() >= debounce_until:
                debounce_until = 0.0
                self._hub.broadcast("change")

    def start(self) -> None:
        Handler = self._build_handler()
        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.port = self._server.server_address[1]
        self._serve_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._serve_thread.start()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()


_HOT_RELOAD_SCRIPT = b"""<script>
(function () {
  if (typeof EventSource === "undefined") return;
  var es = new EventSource("/events");
  es.addEventListener("change", function () { location.reload(); });
})();
</script>"""


class DashboardServer:
    """Serves ~/.work/viz/ over HTTP, regenerating dashboard + per-workspace pages on demand,
    with SSE-driven hot-reload when files under workspaces_root change.

    Designed to bypass snap-confined browsers' file:// restrictions by exposing the same content
    over http://127.0.0.1:<port>/. Stdlib only.
    """

    def __init__(self, workspaces_root: Path, port: int = 0,
                 viz_dir: Optional[Path] = None) -> None:
        self.workspaces_root = workspaces_root
        self.viz_dir = viz_dir or (Path.home() / ".work" / "viz")
        self.port = port or _pick_port(preferred_range=(8800, 8810))
        self._hub = _SSEHub()
        self._server: Optional[ThreadingHTTPServer] = None
        self._serve_thread: Optional[threading.Thread] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _build_handler(self):
        viz_dir = self.viz_dir
        workspaces_root = self.workspaces_root
        hub = self._hub

        # Track when we last regenerated to avoid hammering on rapid asset requests.
        regen_lock = threading.Lock()
        last_regen = [0.0]
        REGEN_DEBOUNCE = 1.0  # seconds

        def maybe_regen():
            with regen_lock:
                now = time.monotonic()
                if now - last_regen[0] < REGEN_DEBOUNCE:
                    return
                last_regen[0] = now
            try:
                from .generator import generate_dashboard
                generate_dashboard(workspaces_root, out_dir=viz_dir)
            except Exception as exc:
                print(f"warning: regenerate failed: {exc}")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args, **_kwargs):
                return

            def do_GET(self):
                if self.path == "/events":
                    self._serve_sse(hub)
                    return
                # Regenerate when the user lands on / or /dashboard.html (cheap snapshot).
                if self.path in ("/", "/dashboard.html", "/index.html"):
                    maybe_regen()
                    target = viz_dir / "dashboard.html"
                    if target.is_file():
                        self._send_html(target)
                        return
                    self.send_error(HTTPStatus.NOT_FOUND, "dashboard.html missing; run install.sh first")
                    return

                # Workspace pages: regenerate then serve.
                if self.path.endswith(".html") and "/" not in self.path[1:]:
                    rel = self.path.lstrip("/")
                    maybe_regen()
                    target = viz_dir / rel
                    if target.is_file():
                        self._send_html(target)
                        return
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return

                # Vendor assets: serve raw, with traversal protection.
                if self.path.startswith("/vendor/"):
                    rel = self.path[len("/vendor/"):]
                    base = (viz_dir / "vendor").resolve()
                    try:
                        fp = (base / rel).resolve()
                        fp.relative_to(base)
                    except (ValueError, OSError):
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
                    if fp.is_file():
                        ctype = "text/javascript" if fp.suffix == ".js" else "text/css"
                        self._send_file(fp, ctype)
                        return

                self.send_error(HTTPStatus.NOT_FOUND)

            def _send_html(self, fp: Path):
                """Inject the hot-reload SSE script before </body> and serve the result."""
                data = fp.read_bytes()
                injected = data.replace(b"</body>", _HOT_RELOAD_SCRIPT + b"</body>", 1)
                if injected == data:
                    injected = data + _HOT_RELOAD_SCRIPT
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(injected)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(injected)

            def _send_file(self, fp: Path, ctype: str):
                data = fp.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def _serve_sse(self, hub: "_SSEHub"):
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                try:
                    self.wfile.write(b": connected\n\n")
                    self.wfile.flush()
                except OSError:
                    return
                q = hub.register()
                try:
                    while True:
                        try:
                            event = q.get(timeout=15)
                            payload = f"event: change\ndata: {event}\n\n"
                            self.wfile.write(payload.encode("utf-8"))
                            self.wfile.flush()
                        except Empty:
                            try:
                                self.wfile.write(b": keepalive\n\n")
                                self.wfile.flush()
                            except OSError:
                                break
                        except OSError:
                            break
                finally:
                    hub.unregister(q)

        return Handler

    def _watch_loop(self):
        target = self.workspaces_root
        prev = _scan_mtimes(target)
        debounce_until = 0.0
        while not self._stop_event.wait(1.0):
            now = _scan_mtimes(target)
            if now != prev:
                debounce_until = time.monotonic() + 0.25
                prev = now
            if debounce_until and time.monotonic() >= debounce_until:
                debounce_until = 0.0
                self._hub.broadcast("change")

    def start(self) -> None:
        Handler = self._build_handler()
        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.port = self._server.server_address[1]
        self._serve_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._serve_thread.start()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
