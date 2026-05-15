"""Thin static file server over a generated out_dir."""
from __future__ import annotations
import functools
import http.server
import socketserver
import webbrowser
from pathlib import Path


def _make_server(out_dir: Path, host: str, port: int) -> socketserver.TCPServer:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out_dir))
    return socketserver.TCPServer((host, port), handler)


def serve(out_dir: Path, host: str = "127.0.0.1", port: int = 0,
          open_browser: bool = True) -> None:
    httpd = _make_server(Path(out_dir), host, port)
    actual_port = httpd.server_address[1]
    url = f"http://{host}:{actual_port}/index.html"
    print(f"work-viz serve: {url}")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("stopping")
    finally:
        httpd.shutdown()
