"""Archon tailer — background thread that polls adapters and appends new
events to the store (which fans them out to SSE subscribers).
"""

from __future__ import annotations

import threading
from typing import Any

from .store import EventStore


class Tailer(threading.Thread):
    def __init__(
        self,
        adapters: dict[str, Any],
        store: EventStore,
        interval: float = 2.0,
    ):
        super().__init__(daemon=True, name="archon-tailer")
        self.adapters = adapters
        self.store = store
        self.interval = interval
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            for adapter in list(self.adapters.values()):
                try:
                    for event in adapter.poll():
                        self.store.append(event)
                except Exception:
                    # never let one bad poll kill the tailer
                    continue
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()
