"""Archon event store — in-memory ring buffer with optional JSONL persistence."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any


class EventStore:
    """Append-only event store. Keeps a bounded in-memory buffer and, when a
    path is given, persists every event as one JSON line (crash-safe append).
    """

    def __init__(self, path: str | Path | None = None, max_mem: int = 10_000):
        self.max_mem = max_mem
        self.path = Path(path) if path else None
        self._events: deque[dict[str, Any]] = deque(maxlen=max_mem)
        if self.path is not None and self.path.exists():
            self._load()

    def _load(self) -> None:
        try:
            data = self.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        for line in data.splitlines():
            if not line.strip():
                continue
            try:
                self._events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        self._events.append(event)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, separators=(",", ":"), sort_keys=True))
                f.write("\n")
        return event

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(self._events)[-limit:]

    def since(self, ts: str | None, limit: int = 500) -> list[dict[str, Any]]:
        items = list(self._events)
        if ts:
            items = [e for e in items if str(e.get("ts", "")) > ts]
        return items[-limit:]

    def count(self) -> int:
        return len(self._events)
