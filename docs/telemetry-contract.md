# Archon telemetry contract v0.1

Adapters translate framework-specific logs into this JSON event stream.
The dashboard and control API consume **only** this contract. Adding a new
framework = writing one adapter; nothing else changes.

## Transport

- Self-hosted: adapters write events to a local file or HTTP endpoint
  (`POST /events`) that Archon's server tails.
- Hosted (future): agents stream over HTTPS/WSS with a bearer token.

## Event envelope

Every event is a single JSON object with `v`, `ts`, `type`, and a
type-specific payload. Timestamps are ISO-8601 UTC.

```json
{"v": 1, "ts": "2026-08-17T00:00:00Z", "type": "agent.session_started", "agent": "main", "session_id": "aabb0c04"}
```

## Event types (v0.1)

### agent.session_started / agent.session_ended
```json
{"type": "agent.session_started", "agent": "main", "session_id": "aabb0c04", "channel": "webchat"}
{"type": "agent.session_ended",   "agent": "main", "session_id": "aabb0c04", "reason": "idle_timeout"}
```

### agent.message
```json
{"type": "agent.message", "agent": "main", "session_id": "aabb0c04", "role": "user|assistant|system", "text": "…"}
```

### agent.state
```json
{"type": "agent.state", "agent": "main", "session_id": "aabb0c04", "state": "idle|working|error|paused", "detail": "optional"}
```

### automation.state
```json
{"type": "automation.state", "automation": "make:6927828", "state": "active|inactive|error", "next_run": "2026-08-19T09:00:00Z"}
```

### service.health
```json
{"type": "service.health", "service": "trading-monitor", "state": "up|down|degraded", "since": "2026-08-16T21:00:00Z"}
```

### control.request / control.result
```json
{"type": "control.request", "action": "killswitch|start|stop|restart", "target": "automation:make:6927828", "by": "user"}
{"type": "control.result",  "request_id": "…", "ok": true, "detail": "stopped"}
```

## Adapter requirements

1. Emit `agent.session_started` when a session begins, `agent.session_ended`
   when it ends (with reason).
2. Emit `agent.state` on transitions; at minimum on entering `error`.
3. Emit `automation.state` for schedulers/automations under management.
4. Emit `service.health` at startup and on change (or every heartbeat).

## Validation

Events are validated against this spec (version + type + required fields).
Unknown types are dropped with a warning — forward-compatible by design.
