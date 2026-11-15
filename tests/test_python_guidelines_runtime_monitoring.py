"""Offline monitoring, logging ownership and security configuration contracts."""

import asyncio
import logging
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from test_python_guidelines_runtime import load_module as load_module


@pytest.fixture
def runtime_module(load_module, tmp_path):
    load_module.stub("app.config.app_config", settings=SimpleNamespace(
        system=SimpleNamespace(logs_dir=tmp_path),
        security=SimpleNamespace(jwt_secret_key="offline-shared-secret-for-tests"),
    ))
    return load_module


def test_monitor_sampling_runs_off_loop(runtime_module):
    sampled_threads = []

    def sample_cpu(interval):
        sampled_threads.append(threading.get_ident())
        return 25

    runtime_module.stub("psutil", cpu_percent=sample_cpu,
        virtual_memory=lambda: SimpleNamespace(percent=50),
        disk_usage=lambda _: SimpleNamespace(percent=40),
        net_io_counters=lambda: SimpleNamespace(bytes_sent=0, bytes_recv=1))
    module = runtime_module("app/agents/framework/monitoring/monitor.py")
    monitor = module.SystemMonitor({"thresholds": {}})
    asyncio.run(monitor._collect_system_metrics())
    assert sampled_threads and sampled_threads[0] != threading.get_ident()
    assert monitor.get_metrics("system.cpu_usage")[0].value == 0.25


def test_monitor_failure_still_waits_before_retry(runtime_module, monkeypatch):
    module = runtime_module("app/agents/framework/monitoring/monitor.py")
    monitor = module.SystemMonitor({"interval": 7})
    calls = []
    delays = []

    async def fail():
        calls.append(1)
        if len(calls) == 2:
            monitor.monitoring = False
        raise OSError("sampling failed")

    async def pause(delay):
        delays.append(delay)
        monitor.monitoring = False

    monkeypatch.setattr(monitor, "_collect_system_metrics", fail)
    monkeypatch.setattr(module.asyncio, "sleep", pause)
    monitor.monitoring = True
    asyncio.run(monitor._monitoring_loop())
    assert calls == [1]
    assert delays == [7]


def test_monitor_zero_history_windows_stay_empty(runtime_module):
    module = runtime_module("app/agents/framework/monitoring/monitor.py")
    metric = module.Metric("test", 1, datetime.now() - timedelta(seconds=1), {})
    monitor = module.SystemMonitor()
    monitor.metrics["test"].append(metric)
    assert monitor.get_metrics("test", duration=timedelta(0)) == []
    manager = module.AlertManager()
    manager.alert_history.append(module.Alert("WARNING", "test", datetime.now(), metric, 0))
    assert manager.get_recent_alerts(limit=0) == []


def test_monitor_stop_finishes_cleanup_in_cancelled_scope(runtime_module):
    import anyio

    module = runtime_module("app/agents/framework/monitoring/monitor.py")
    monitor = module.SystemMonitor()

    async def run():
        started = asyncio.Event()
        closed = []

        async def sampling():
            try:
                started.set()
                await asyncio.Event().wait()
            finally:
                await anyio.lowlevel.checkpoint()
                closed.append(True)

        task = asyncio.create_task(sampling())
        monitor._monitor_task = task
        await started.wait()
        stopped = False
        with anyio.CancelScope() as scope:
            scope.cancel()
            await monitor.stop()
            stopped = True
        assert stopped
        assert closed == [True]
        assert task.done()

    asyncio.run(run())


def smtp_configuration():
    return {"host": "smtp.invalid", "port": 587, "username": "test", "password": "test",
            "from_addr": "from@example.test", "to_addrs": ["to@example.test"]}


def test_monitor_email_uses_worker_and_finite_timeout(runtime_module, monkeypatch):
    import smtplib

    module = runtime_module("app/agents/framework/monitoring/monitor.py")
    opened_threads = []
    transport = MagicMock()
    transport.__enter__.return_value = transport

    def connect(*args, **kwargs):
        opened_threads.append(threading.get_ident())
        assert kwargs["timeout"] > 0
        return transport

    monkeypatch.setattr(smtplib, "SMTP", connect)
    metric = module.Metric("test", 1, datetime.now(), {})
    alert = module.Alert("WARNING", "test", datetime.now(), metric, 0)
    asyncio.run(module.EmailAlertChannel(smtp_configuration()).send(alert))
    assert opened_threads and opened_threads[0] != threading.get_ident()
    transport.send_message.assert_called_once()
    transport.__exit__.assert_called_once()


def test_monitor_email_failure_remains_visible(runtime_module, monkeypatch):
    import smtplib

    module = runtime_module("app/agents/framework/monitoring/monitor.py")
    monkeypatch.setattr(smtplib, "SMTP", Mock(side_effect=OSError("mail unavailable")))
    metric = module.Metric("test", 1, datetime.now(), {})
    alert = module.Alert("WARNING", "test", datetime.now(), metric, 0)
    with pytest.raises(OSError, match="mail unavailable"):
        asyncio.run(module.EmailAlertChannel(smtp_configuration()).send(alert))


@pytest.mark.parametrize("path,class_name", [
    ("monitoring/monitor.py", "LogAlertChannel"),
    ("security/gateway.py", "AuditLogger"),
])
def test_owned_log_handlers_close_without_closing_borrowed(runtime_module, monkeypatch, path, class_name):
    module = runtime_module("app/agents/framework/" + path)
    shared_logger = logging.Logger("offline-runtime-audit")
    borrowed = Mock(spec=logging.Handler)
    borrowed.level = logging.NOTSET
    shared_logger.addHandler(borrowed)
    monkeypatch.setattr(module.logging, "getLogger", lambda *args: shared_logger)
    owner = getattr(module, class_name)()
    owned = [handler for handler in shared_logger.handlers if handler is not borrowed]
    assert len(owned) == 1
    assert isinstance(owned[0], logging.StreamHandler)
    stream = owned[0].stream
    try:
        owner.close()
        owner.close()
        assert stream.closed
        assert shared_logger.handlers == [borrowed]
        borrowed.close.assert_not_called()
    finally:
        shared_logger.removeHandler(owned[0])
        owned[0].close()


def test_gateway_uses_shared_secret_with_explicit_environment_override(runtime_module, monkeypatch):
    module = runtime_module("app/agents/framework/security/gateway.py")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    assert module.AuthenticationManager().jwt_secret == "offline-shared-secret-for-tests"
    monkeypatch.setenv("JWT_SECRET", "explicit-test-secret")
    assert module.AuthenticationManager().jwt_secret == "explicit-test-secret"


def test_gateway_import_does_not_configure_process_logging(runtime_module, monkeypatch):
    configure = Mock()
    monkeypatch.setattr(logging, "basicConfig", configure)
    runtime_module("app/agents/framework/security/gateway.py")
    configure.assert_not_called()


def test_gateway_failure_keeps_original_cause(runtime_module):
    module = runtime_module("app/agents/framework/security/gateway.py")
    gateway = object.__new__(module.SecurityGateway)
    failure = ValueError("broken authentication provider")
    gateway.auth_manager = SimpleNamespace(authenticate=AsyncMock(side_effect=failure))
    with pytest.raises(module.SecurityError) as error:
        asyncio.run(gateway.process_request({"query": "policy"}))
    assert error.value.__cause__ is failure


def test_auth_failure_log_contains_no_token_fragment(runtime_module):
    module = runtime_module("app/agents/framework/security/gateway.py")
    audit = object.__new__(module.AuditLogger)
    audit.logger = Mock()
    token = "sensitive-token-prefix-and-signature"
    audit.log_auth_failure({"token": token}, "request")
    assert token[:20] not in str(audit.logger.warning.call_args)


def test_empty_action_cannot_bypass_authorization(runtime_module):
    module = runtime_module("app/agents/framework/security/gateway.py")
    manager = module.AuthorizationManager()
    user = module.User("user", "User", [], [])
    assert asyncio.run(manager.authorize(user, "")) is False
