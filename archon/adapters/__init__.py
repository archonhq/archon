"""Archon adapters: translate framework logs into telemetry events, and
controllers that execute control-plane actions."""

from .command import CommandAdapter
from .openclaw import OpenClawAdapter

__all__ = ["OpenClawAdapter", "CommandAdapter"]
