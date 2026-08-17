# Archon

**The control room for your AI agent fleet — see what your agents are doing,
and stop them when they're not.**

Archon is a local-first control plane for people running multiple AI agents
and automations (OpenClaw, Claude Code, CrewAI, Make/n8n scenarios, custom
bots). Most agent tooling only *observes*; Archon also *controls*:

- **See** — every agent session, automation, and service on one pane
- **Control** — kill switches, start/stop automations, restart services
- **Alert** — Telegram/webhook/email on state changes and failures
- **Zero dependencies** — a stdlib Python server + one HTML file

## Status

Pre-alpha (Phase 0). Reference implementation: OpenClaw adapter. The control
plane is proven in production on a live trading-monitor deployment (kill
switch, risk rails, Telegram alerts, VPS health).

## Quick start

*(not yet published)*

```bash
pip install archon
archon serve
# open http://127.0.0.1:8000
```

## Architecture

```
framework logs ──► adapter ──► telemetry events ──► dashboard (HTTP/SSE)
                                        ▲
                                   control API
                                        │
framework APIs ◄─────── executor ◄──────┘
```

Adapters translate framework-specific logs into one JSON event stream
(see [docs/telemetry-contract.md](docs/telemetry-contract.md)). The dashboard
and control API consume only the contract, so a new framework is one adapter
away.

Adapters: OpenClaw (reference) · Make.com · trading monitor · Claude Code
(planned) · CrewAI (planned) · n8n (planned) · generic webhook (planned)

## Roadmap

| Phase | Scope |
|---|---|
| 0 | Telemetry contract, adapters, auth, packaging, landing page |
| 1 | 10–20 self-host users, iterate |
| 2 | Hosted tier (ingest API, multi-tenant, billing) |
| 3 | Trading edition (executor, kill switch, pager) |

## License

MIT
