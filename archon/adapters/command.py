"""Archon command controller — runs pre-configured shell commands.

This is the real control plane: a "kill switch" / start / stop / restart maps
to a shell command the operator has declared in a config file. Commands never
come from client requests — the request only names an action + target, and the
controller looks up the pre-approved command for that pair.
"""

from __future__ import annotations

import subprocess
import uuid
from typing import Any

from ..events import make_event


class CommandAdapter:
    """Control adapter.

    `commands` maps target-prefix -> {action: command}. Example:
        {"openclaw": {"stop": "openclaw gateway stop",
                      "restart": "openclaw gateway restart"}}
    """

    def __init__(self, commands: dict[str, dict[str, str]] | None = None):
        self.commands = commands or {}

    def control(self, action: str, target: str) -> dict:
        prefix = str(target).split(":", 1)[0]
        actions = self.commands.get(prefix, {})
        cmd = actions.get(action)
        if cmd is None and action == "killswitch":
            cmd = actions.get("stop")  # killswitch defaults to stop
        rid = uuid.uuid4().hex[:12]

        if not cmd:
            return make_event(
                "control.result", request_id=rid, ok=False,
                detail=f"no {action} command configured for {prefix!r}",
            )

        try:
            proc = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            return make_event("control.result", request_id=rid, ok=False,
                              detail="command timed out after 30s")
        except Exception as exc:  # noqa: BLE001 — surface, don't crash
            return make_event("control.result", request_id=rid, ok=False,
                              detail=str(exc))

        ok = proc.returncode == 0
        detail = (proc.stdout.strip() or proc.stderr.strip()
                  or f"exit {proc.returncode}")[-200:]
        return make_event("control.result", request_id=rid, ok=ok, detail=detail)
