"""Archon broadcaster — fan-out of new events to SSE subscribers."""

from __future__ import annotations

import queue
import threading
from typing import Any


class Broadcaster:
    """Thread-safe pub/sub for events. Slow consumers are dropped (bounded
    queues) rather than blocking the tailer.
    """

    def __init__(self, maxsize: int = 2000):
        self._subs: list[queue.Queue[Any]] = []
        self._lock = threading.Lock()
        self._maxsize = maxsize

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=self._maxsize)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._subs.remove(q)
            except ValueError:
                pass

    def publish(self, event: dict) -> None:
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass  # drop for slow consumers
