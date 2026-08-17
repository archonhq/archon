"""Tests for the Archon command controller (the kill switch)."""

from archon.adapters import CommandAdapter


def test_runs_configured_command():
    a = CommandAdapter({"svc": {"stop": "echo stopped"}})
    r = a.control("stop", "svc:main")
    assert r["ok"] is True
    assert "stopped" in r["detail"]
    assert r["request_id"]


def test_missing_command_returns_failure():
    a = CommandAdapter({})
    r = a.control("stop", "svc:main")
    assert r["ok"] is False
    assert "no stop command" in r["detail"]


def test_killswitch_falls_back_to_stop():
    a = CommandAdapter({"svc": {"stop": "echo ok"}})
    r = a.control("killswitch", "svc:main")
    assert r["ok"] is True
    assert "ok" in r["detail"]


def test_failed_command_reports_stderr():
    a = CommandAdapter({"svc": {"stop": "python -c 'import sys; sys.exit(3)'"}})
    r = a.control("stop", "svc:main")
    assert r["ok"] is False
