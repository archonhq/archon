"""Archon HTTP server — stdlib-only (zero dependencies).

Routes:
  GET  /                -> dashboard (single-file HTML)
  GET  /api/events      -> recent events (JSON), ?limit= & ?since=ISO
  GET  /api/health      -> {status, events, adapters}
  POST /api/events      -> ingest one validated event
  POST /api/control     -> {action, target, by} -> routed to matching adapter
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from .events import validate
from .store import EventStore

CONTROL_ACTIONS = {"killswitch", "start", "stop", "restart"}

_DEFAULT_DASHBOARD = (
    "<!doctype html><html><body style='font-family:monospace'>"
    "<h1>Archon</h1><p>dashboard not found</p></body></html>"
).encode()


class ArchonHandler(BaseHTTPRequestHandler):
    """Handler bound to a store + adapters + dashboard bytes via factory."""

    store: EventStore
    adapters: dict[str, Any]
    dashboard: bytes

    def log_message(self, *args: Any) -> None:  # silence default logging
        pass

    # -- helpers ---------------------------------------------------------

    def _send(self, body: bytes, code: int, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, code: int = 200) -> None:
        self._send(json.dumps(obj).encode(), code, "application/json; charset=utf-8")

    # -- routes ----------------------------------------------------------

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/":
            self._send(self.dashboard, 200, "text/html; charset=utf-8")
        elif url.path == "/api/events":
            q = parse_qs(url.query)
            limit = int(q.get("limit", ["100"])[0])
            since = q.get("since", [None])[0]
            events = self.store.since(since, limit) if since else self.store.recent(limit)
            self._json({"events": events, "count": self.store.count()})
        elif url.path == "/api/health":
            self._json({
                "status": "ok",
                "events": self.store.count(),
                "adapters": sorted(self.adapters),
            })
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._json({"error": "invalid json"}, 400)

        if url.path == "/api/events":
            try:
                validate(data)
            except ValueError as exc:
                return self._json({"error": str(exc)}, 400)
            self.store.append(data)
            self._json({"ok": True})
        elif url.path == "/api/control":
            self._control(data)
        else:
            self._json({"error": "not found"}, 404)

    def _control(self, data: dict) -> None:
        action = data.get("action")
        target = data.get("target", "")
        by = data.get("by", "user")
        if action not in CONTROL_ACTIONS:
            return self._json({"error": f"unsupported action: {action}"}, 400)

        adapter = None
        prefix = str(target).split(":", 1)[0]
        adapter = self.adapters.get(prefix)

        if adapter is None:
            result = {"ok": False, "detail": f"no adapter for {prefix!r}"}
        else:
            result = adapter.control(action, target)

        self.store.append({
            "v": 1, "type": "control.request", "action": action,
            "target": target, "by": by,
        })
        self.store.append(result)
        self._json(result)


def make_handler(store: EventStore, adapters: dict[str, Any], dashboard: bytes):
    return type(
        "BoundArchonHandler",
        (ArchonHandler,),
        {"store": store, "adapters": adapters, "dashboard": dashboard},
    )


def _load_dashboard(path: str | Path | None) -> bytes:
    if path is not None:
        p = Path(path)
        if p.exists():
            return p.read_bytes()
    bundled = Path(__file__).parent / "dashboard.html"
    if bundled.exists():
        return bundled.read_bytes()
    return _DEFAULT_DASHBOARD


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    store: EventStore | None = None,
    adapters: dict[str, Any] | None = None,
    dashboard: str | Path | None = None,
) -> ThreadingHTTPServer:
    """Create and return a running ThreadingHTTPServer (call serve_forever)."""
    store = store or EventStore()
    adapters = adapters or {}
    handler = make_handler(store, adapters, _load_dashboard(dashboard))
    srv = ThreadingHTTPServer((host, port), handler)
    return srv
