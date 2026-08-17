"""Tests for the Archon broadcaster."""

from archon.broadcast import Broadcaster


def test_subscribe_publish_receive():
    b = Broadcaster()
    q = b.subscribe()
    b.publish({"type": "agent.state", "state": "working"})
    assert q.get_nowait()["state"] == "working"
    b.unsubscribe(q)
    assert b._subs == []


def test_multiple_subscribers():
    b = Broadcaster()
    q1, q2 = b.subscribe(), b.subscribe()
    b.publish({"n": 1})
    assert q1.get_nowait()["n"] == 1
    assert q2.get_nowait()["n"] == 1


def test_unsubscribe_stops_delivery():
    b = Broadcaster()
    q = b.subscribe()
    b.unsubscribe(q)
    b.publish({"n": 2})
    assert q.empty()
