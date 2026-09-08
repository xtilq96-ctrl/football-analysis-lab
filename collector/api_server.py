#!/usr/bin/env python3
"""Minimal signed, read-only HTTP relay for the collector output."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DATA_DIR = Path(os.environ.get("FOOTBALL_AI_DATA_DIR", "/var/lib/football-ai"))
SECRET_FILE = Path(os.environ.get("FOOTBALL_AI_RELAY_SECRET_FILE", "/etc/football-ai/relay-secret"))
HOST = os.environ.get("FOOTBALL_AI_RELAY_HOST", "0.0.0.0")
PORT = int(os.environ.get("FOOTBALL_AI_RELAY_PORT", "80"))
MAX_FILE_SIZE = 2 * 1024 * 1024


class RelayHandler(BaseHTTPRequestHandler):
    server_version = "FootballAIRelay/1.0"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.partition("?")[0]
        if path == "/api/latest":
            self.send_signed_file(DATA_DIR / "latest.json")
            return
        if path == "/api/health":
            self.send_signed_file(DATA_DIR / "health.json")
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_HEAD(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.partition("?")[0]
        if path in {"/api/latest", "/api/health"}:
            self.send_response(HTTPStatus.OK)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def send_signed_file(self, path: Path) -> None:
        try:
            body = path.read_bytes()
            if len(body) > MAX_FILE_SIZE:
                raise ValueError("data file is too large")
            secret = SECRET_FILE.read_bytes().strip()
            if len(secret) < 32:
                raise ValueError("relay secret is invalid")
            signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
        except (OSError, ValueError) as error:
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Football-Signature", signature)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: HTTPStatus, payload: dict[str, str]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} {format % args}", flush=True)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), RelayHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
