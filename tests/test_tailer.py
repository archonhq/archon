"""Tests for the Archon tailer + adapter poll() delta behavior."""

import json
import time

from archon.adapters import OpenClawAdapter
from archon.store import EventStore
from archon.tailer import Tailer


def _msg(text):
    return json.dumps({
        "id": "1", "type": "message",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    })


def test_adapter_poll_delta(tmp_path):
    path = tmp_path / "abc123.jsonl"
    path.write_text(_msg("first") + "\n", encoding="utf-8")

    adapter = OpenClawAdapter(tmp_path)
    snapshot = list(adapter.iter_events())
    assert len(snapshot) == 1
    assert snapshot[0]["text"] == "first"

    # nothing new yet
    assert list(adapter.poll()) == []

    # append a new line -> poll yields exactly one new event
    with path.open("a", encoding="utf-8") as f:
        f.write(_msg("second") + "\n")
    new = list(adapter.poll())
    assert len(new) == 1
    assert new[0]["text"] == "second"


def test_tailer_picks_up_new_events(tmp_path):
    path = tmp_path / "abc123.jsonl"
    path.write_text(_msg("seed") + "\n", encoding="utf-8")

    adapter = OpenClawAdapter(tmp_path)
    store = EventStore()
    for ev in adapter.iter_events():
        store.append(ev)
    assert store.count() == 1

    tailer = Tailer({"openclaw": adapter}, store, interval=0.05)
    tailer.start()

    with path.open("a", encoding="utf-8") as f:
        f.write(_msg("live") + "\n")

    deadline = time.time() + 3.0
    while time.time() < deadline and store.count() < 2:
        time.sleep(0.05)

    tailer.stop()
    assert store.count() >= 2
    assert store.recent()[-1]["text"] == "live"
