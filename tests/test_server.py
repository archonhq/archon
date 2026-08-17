"""Tests for the Archon HTTP server (stdlib, no framework)."""

import json
import http.client
import threading
import urllib.error
import urllib.request

import pytest

from archon.events import make_event
from archon.server import serve
from archon.store import EventStore


@pytest.fixture()
def client():
    store = EventStore()
    srv = serve(host="127.0.0.1", port=0, store=store, adapters={})
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}", store
    srv.shutdown()
    srv.server_close()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read())


def _post(base, path, obj):
    req = urllib.request.Request(
        base + path, data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


def test_health(client):
    base, store = client
    h = _get(base, "/api/health")
    assert h["status"] == "ok"
    assert h["events"] == 0
    assert h["adapters"] == []


def test_ingest_and_query(client):
    base, store = client
    ok = _post(base, "/api/events", make_event("service.health", service="x", state="up"))
    assert ok["ok"] is True
    assert store.count() == 1
    data = _get(base, "/api/events")
    assert data["count"] == 1
    assert data["events"][0]["type"] == "service.health"


def test_ingest_rejects_invalid(client):
    base, store = client
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(base, "/api/events", {"v": 1, "type": "agent.state", "state": "bogus"})
    assert exc.value.code == 400
    assert store.count() == 0


def test_control_no_controller(client):
    base, store = client
    res = _post(base, "/api/control", {"action": "stop", "target": "openclaw:main"})
    assert res["ok"] is False
    assert "no controller" in res["detail"]
    # control.request + control.result were both stored
    assert store.count() == 2


def test_control_bad_action(client):
    base, store = client
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(base, "/api/control", {"action": "rm-rf", "target": "x"})
    assert exc.value.code == 400


def test_control_routes_to_controller():
    from archon.adapters import CommandAdapter

    store = EventStore()
    srv = serve(
        host="127.0.0.1", port=0, store=store, adapters={},
        controllers={"svc": CommandAdapter({"svc": {"stop": "echo done"}})},
    )
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"
    try:
        res = _post(base, "/api/control", {"action": "stop", "target": "svc:main"})
        assert res["ok"] is True
        assert "done" in res["detail"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_dashboard_served(client):
    base, store = client
    with urllib.request.urlopen(base + "/", timeout=5) as r:
        body = r.read().decode()
    assert "Archon" in body


def test_sse_stream(client):
    base, store = client
    port = int(base.rsplit(":", 1)[1])
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/api/events/stream")
    resp = conn.getresponse()
    assert resp.status == 200
    assert resp.getheader("Content-Type") == "text/event-stream"

    # publish an event via the ingest endpoint
    _post(base, "/api/events", make_event("service.health", service="sse", state="up"))

    # socket timeout already set at connect; readline returns on data
    line = resp.fp.readline()
    assert line.startswith(b"data:")
    payload = json.loads(line[len(b"data:"):].strip())
    assert payload["type"] == "service.health"
    assert payload["service"] == "sse"
    conn.close()
