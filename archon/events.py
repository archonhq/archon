"""Archon telemetry contract v0.1 — event schema and validation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

CONTRACT_VERSION = 1

# type -> required fields (beyond v/ts/type)
REQUIRED_FIELDS: dict[str, set[str]] = {
    "agent.session_started": {"agent", "session_id"},
    "agent.session_ended": {"agent", "session_id", "reason"},
    "agent.message": {"agent", "session_id", "role", "text"},
    "agent.state": {"agent", "session_id", "state"},
    "automation.state": {"automation", "state"},
    "service.health": {"service", "state"},
    "control.request": {"action", "target", "by"},
    "control.result": {"request_id", "ok"},
}

VALID_STATES = {
    "agent.state": {"idle", "working", "error", "paused"},
    "automation.state": {"active", "inactive", "error"},
    "service.health": {"up", "down", "degraded"},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_event(type_: str, **fields: Any) -> dict[str, Any]:
    """Build a valid event, filling ts/version automatically."""
    event = {"v": CONTRACT_VERSION, "ts": now_iso(), "type": type_}
    event.update(fields)
    validate(event)
    return event


def validate(event: dict[str, Any]) -> None:
    """Raise ValueError on invalid events."""
    if event.get("v") != CONTRACT_VERSION:
        raise ValueError(f"unsupported contract version: {event.get('v')}")
    if "ts" not in event:
        raise ValueError("missing ts")
    etype = event.get("type")
    required = REQUIRED_FIELDS.get(etype)
    if required is None:
        raise ValueError(f"unknown event type: {etype}")
    missing = required - set(event)
    if missing:
        raise ValueError(f"{etype}: missing fields {sorted(missing)}")
    states = VALID_STATES.get(etype)
    if states and event["state"] not in states:
        raise ValueError(f"{etype}: invalid state {event['state']!r}")


def dumps(event: dict[str, Any]) -> str:
    validate(event)
    return json.dumps(event, separators=(",", ":"), sort_keys=True)


def loads(line: str) -> dict[str, Any]:
    event = json.loads(line)
    validate(event)
    return event
