from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.paper.web_status import build_paper_status_payload, render_paper_status_html


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the Paper Trading status page.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--state-path", type=Path, default=Path("runtime/paper-state.json"))
    parser.add_argument("--error-log-path", type=Path, default=Path("runtime/logs/paper-realtime.log"))
    return parser.parse_args()


def make_handler(state_path: Path, error_log_path: Path):
    class PaperStatusHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            payload = build_paper_status_payload(state_path, error_log_path=error_log_path)
            if self.path == "/api/status":
                self._send_json(payload)
                return
            if self.path in {"/", "/index.html"}:
                self._send_html(render_paper_status_html(payload))
                return
            self.send_error(404)

        def log_message(self, format: str, *args) -> None:
            return

        def _send_html(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, payload: dict) -> None:
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return PaperStatusHandler


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.state_path, args.error_log_path))
    print(f"Paper status page: http://{args.host}:{args.port}")
    print(f"Reading state: {args.state_path}")
    print(f"Reading error log: {args.error_log_path}")
    server.serve_forever()


if __name__ == "__main__":
    main()
