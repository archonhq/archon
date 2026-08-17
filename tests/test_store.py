"""Tests for the Archon event store."""

import json

from archon.events import make_event
from archon.store import EventStore


def test_in_memory_recent_and_count():
    store = EventStore()
    assert store.count() == 0
    store.append(make_event("service.health", service="x", state="up"))
    store.append(make_event("agent.state", agent="main", session_id="s", state="working"))
    assert store.count() == 2
    assert store.recent(1)[0]["type"] == "agent.state"


def test_persistence_roundtrip(tmp_path):
    path = tmp_path / "events.jsonl"
    store = EventStore(path=path)
    store.append(make_event("service.health", service="x", state="up"))
    store.append(make_event("agent.state", agent="main", session_id="s", state="idle"))

    reopened = EventStore(path=path)
    assert reopened.count() == 2
    assert reopened.recent()[-1]["type"] == "agent.state"


def test_since_filter():
    store = EventStore()
    store.append(make_event("service.health", service="a", state="up"))
    # an ancient timestamp returns everything after it
    assert len(store.since("2000-01-01T00:00:00Z")) == 1
    # a future timestamp returns nothing
    assert store.since("2999-01-01T00:00:00Z") == []
