from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs


def create_handler(render_page_fn, handle_post_fn, api_builder):
    class Handler(BaseHTTPRequestHandler):
        def _read_form(self) -> dict[str, list[str]]:
            ln = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(ln).decode("utf-8", errors="replace")
            return parse_qs(raw, keep_blank_values=True)

        def _respond_html(self, body: bytes, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._respond_html(render_page_fn())

        def do_POST(self):
            form = self._read_form()
            alert = handle_post_fn(self.path, form, api_builder())
            self._respond_html(render_page_fn(alert=alert))

    return Handler
