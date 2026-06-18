"""Serve the HTML dashboard and rebuild data on start."""

from __future__ import annotations

import http.server
import socketserver
import webbrowser
from pathlib import Path

from build_data import main as build_main

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
PORT = 8080


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)


def main() -> None:
    print("Building data from spreadsheets…")
    build_main()
    print(f"Serving at http://localhost:{PORT}")
    webbrowser.open(f"http://localhost:{PORT}")
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
