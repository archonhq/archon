"""OpenClaw adapter — reference implementation.

Reads OpenClaw session JSONL files and emits Archon telemetry events.

Real record shape (OpenClaw `agents/<agent>/sessions/<id>.jsonl`):
    {"id": ..., "type": "message", "parentId": ..., "timestamp": ...,
     "message": {"role": "user|assistant|...", "content": [...], "model": ...}}

The session id is the filename stem, not a field in the record.

Two entry points:
  - `iter_events()` -> full snapshot (seeds a store, then leaves a byte-offset
    cursor so subsequent `poll()` calls only yield new lines)
  - `poll()` -> new events since the last poll (byte-offset tailing)
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
        self._offsets: dict[str, int] = {}  # path -> bytes consumed

    def _session_files(self) -> list[Path]:
        if not self.sessions_dir.is_dir():
            return []
        return sorted(
            p for p in self.sessions_dir.glob("*.jsonl")
            if ".trajectory" not in p.name
        )

    def iter_events(self) -> Iterator[dict]:
        """Snapshot: emit all current events, then arm byte-offset cursors."""
        for path in self._session_files():
            data = self._read_bytes(path, 0)
            session_id = path.stem
            for line in data.splitlines():
                event = self._line_event(line, session_id)
                if event is not None:
                    yield event
            self._offsets[str(path)] = len(data)

    def poll(self) -> Iterator[dict]:
        """Emit only events appended since the last call (byte-offset tail)."""
        for path in self._session_files():
            key = str(path)
            offset = self._offsets.get(key, 0)
            size = path.stat().st_size if path.exists() else 0
            if size < offset:
                offset = 0  # truncated / rotated
            if size == offset:
                continue
            data = self._read_bytes(path, offset)
            if not data:
                continue
            # advance only through the last complete line (keep partial tail)
            newline = data.rfind(b"\n")
            if newline == -1:
                continue
            complete = data[: newline + 1]
            self._offsets[key] = offset + len(complete)
            session_id = path.stem
            for line in complete.decode("utf-8", "replace").splitlines():
                event = self._line_event(line, session_id)
                if event is not None:
                    yield event

    # -- internals ------------------------------------------------------

    @staticmethod
    def _read_bytes(path: Path, offset: int) -> bytes:
        try:
            with path.open("rb") as f:
                f.seek(offset)
                return f.read()
        except OSError:
            return b""

    def _line_event(self, line: str, session_id: str) -> dict | None:
        try:
            raw = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        event = self._translate(raw, session_id)
        if event is None:
            return None
        try:
            validate(event)
        except ValueError:
            return None
        return event

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
