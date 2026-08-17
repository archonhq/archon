"""Archon CLI — `archon serve` (Phase 0.5) and `archon tail` (now)."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="archon", description=__doc__)
    sub = parser.add_subparsers(dest="command")

    tail = sub.add_parser("tail", help="tail an OpenClaw sessions dir as events")
    tail.add_argument("sessions_dir")
    tail.add_argument("--agent", default="main")

    sub.add_parser("serve", help="start the dashboard server (Phase 0.5)")

    args = parser.parse_args(argv)
    if args.command == "tail":
        from .adapters import OpenClawAdapter

        for event in OpenClawAdapter(args.sessions_dir, agent=args.agent).iter_events():
            import json

            print(json.dumps(event))
        return 0
    if args.command == "serve":
        print("serve: not wired yet (Phase 0.5)", file=sys.stderr)
        return 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
