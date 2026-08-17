"""OpenClaw adapter — reference implementation.

Tails OpenClaw session JSONL files and emits Archon telemetry events.

Contract: every adapter exposes `iter_events()` yielding validated event
dicts, and `control(action, target)` for control-plane operations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from ..events import make_event, validate

# session file -> event type mapping (best-effort)
_SESSION_EVENT = {
    "session_started": "agent.session_started",
    "session_ended": "agent.session_ended",
    "message": "agent.message",
    "agent_state": "agent.state",
}


class OpenClawAdapter:
    def __init__(self, sessions_dir: str | Path, agent: str = "main"):
        self.sessions_dir = Path(sessions_dir)
        self.agent = agent

    def iter_events(self) -> Iterator[dict]:
        """Yield validated events from all session JSONL files (tail-lite)."""
        for path in sorted(self.sessions_dir.glob("*.jsonl")):
            for line in self._tail(path):
                try:
                    raw = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                event = self._translate(raw)
                if event is not None:
                    try:
                        validate(event)
                    except ValueError:
                        continue
                    yield event

    def control(self, action: str, target: str) -> dict:
        """Control-plane stub — wired to OpenClaw's API in Phase 0.5."""
        if action not in {"killswitch", "start", "stop", "restart"}:
            raise ValueError(f"unsupported action: {action}")
        # TODO: real OpenClaw control API integration
        return make_event(
            "control.result", request_id="stub", ok=False,
            detail="not wired yet",
        )

    # -- internals ------------------------------------------------------

    @staticmethod
    def _tail(path: Path, max_lines: int = 20_000) -> list[str]:
        """Read the last max_lines lines (crash-safe; no file lock needed)."""
        try:
            data = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return data.splitlines()[-max_lines:]

    def _translate(self, raw: dict) -> dict | None:
        """Translate one OpenClaw JSONL record into a contract event."""
        etype = _SESSION_EVENT.get(raw.get("type", ""))
        if etype is None:
            return None
        if etype == "agent.message":
            return make_event(
                etype, agent=self.agent,
                session_id=str(raw.get("session_id", "")),
                role=raw.get("role", "assistant"),
                text=str(raw.get("text", "")),
            )
        return make_event(
            etype, agent=self.agent,
            session_id=str(raw.get("session_id", "")),
            **{k: raw[k] for k in ("reason", "state") if k in raw},
        )
