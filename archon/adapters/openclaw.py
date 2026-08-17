"""OpenClaw adapter — reference implementation.

Tails OpenClaw session JSONL files and emits Archon telemetry events.

Real record shape (OpenClaw `agents/<agent>/sessions/<id>.jsonl`):
    {"id": ..., "type": "message", "parentId": ..., "timestamp": ...,
     "message": {"role": "user|assistant|...", "content": [...], "model": ...}}

The session id is the filename stem, not a field in the record.

Contract: every adapter exposes `iter_events()` yielding validated event
dicts, and `control(action, target)` for control-plane operations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from ..events import make_event, validate

# OpenClaw record "type" -> Archon event type
_SESSION_EVENT = {
    "session": "agent.session_started",
    "message": "agent.message",
}


class OpenClawAdapter:
    def __init__(self, sessions_dir: str | Path, agent: str = "main"):
        self.sessions_dir = Path(sessions_dir)
        self.agent = agent

    def _session_files(self) -> list[Path]:
        if not self.sessions_dir.is_dir():
            return []
        files = [
            p for p in self.sessions_dir.glob("*.jsonl")
            if ".trajectory" not in p.name
        ]
        return sorted(files)

    def iter_events(self) -> Iterator[dict]:
        """Yield validated events from all session JSONL files (tail-lite)."""
        for path in self._session_files():
            session_id = path.stem
            for line in self._tail(path):
                try:
                    raw = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                event = self._translate(raw, session_id)
                if event is not None:
                    try:
                        validate(event)
                    except ValueError:
                        continue
                    yield event

    def control(self, action: str, target: str) -> dict:
        """Control-plane stub — wired to OpenClaw's API in a later phase."""
        if action not in {"killswitch", "start", "stop", "restart"}:
            raise ValueError(f"unsupported action: {action}")
        return make_event(
            "control.result", request_id="stub", ok=False,
            detail="control not wired to OpenClaw API yet",
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

    def _translate(self, raw: dict, session_id: str) -> dict | None:
        etype = _SESSION_EVENT.get(raw.get("type", ""))
        if etype is None:
            return None
        if etype == "agent.session_started":
            return make_event(etype, agent=self.agent, session_id=session_id)
        if etype == "agent.message":
            msg = raw.get("message")
            if not isinstance(msg, dict):
                return None
            return make_event(
                etype, agent=self.agent, session_id=session_id,
                role=msg.get("role", "assistant"),
                text=self._extract_text(msg.get("content")),
            )
        return None

    @staticmethod
    def _extract_text(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
                elif block.get("type") == "toolCall":
                    name = block.get("name") or block.get("id") or "tool"
                    parts.append(f"[tool:{name}]")
            return " ".join(parts)
        return str(content or "")
