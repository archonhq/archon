"""Archon CLI — `archon tail` (events) and `archon serve` (dashboard)."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="archon", description=__doc__)
    sub = parser.add_subparsers(dest="command")

    tail = sub.add_parser("tail", help="tail an OpenClaw sessions dir as events")
    tail.add_argument("sessions_dir")
    tail.add_argument("--agent", default="main")

    serve = sub.add_parser("serve", help="start the dashboard server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--sessions-dir", default=None, help="OpenClaw sessions dir to seed events from")
    serve.add_argument("--events-file", default=None, help="JSONL file to persist events")

    args = parser.parse_args(argv)

    if args.command == "tail":
        return _tail(args)
    if args.command == "serve":
        return _serve(args)
    parser.print_help()
    return 0


def _tail(args) -> int:
    from .adapters import OpenClawAdapter

    for event in OpenClawAdapter(args.sessions_dir, agent=args.agent).iter_events():
        print(json.dumps(event))
    return 0


def _serve(args) -> int:
    from .adapters import OpenClawAdapter
    from .server import serve
    from .store import EventStore

    store = EventStore(path=args.events_file)
    adapters = {}
    if args.sessions_dir:
        adapters["openclaw"] = OpenClawAdapter(args.sessions_dir)

    # Seed the store from adapters (best-effort, tail-lite).
    for adapter in adapters.values():
        for event in adapter.iter_events():
            store.append(event)

    srv = serve(host=args.host, port=args.port, store=store, adapters=adapters)
    url = f"http://{args.host}:{args.port}"
    print(f"Archon serving {url}  (events={store.count()}, adapters={sorted(adapters) or ['none']})",
          file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
