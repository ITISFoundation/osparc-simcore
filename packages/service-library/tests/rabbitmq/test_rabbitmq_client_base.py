# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# ruff: noqa: SLF001

"""Unit tests for RabbitMQClientBase callback methods.

These tests do NOT require a running RabbitMQ server.
They verify the health-state logic of the synchronous callback methods.
"""

import asyncio
from unittest.mock import MagicMock

import aiormq
import pytest
from servicelib.rabbitmq._client_base import RabbitMQClientBase
from settings_library.rabbit import RabbitSettings

# Mark all tests so the autouse cleanup_check_rabbitmq_server_has_no_errors
# fixture (which requires a live rabbit container) skips its teardown check.
pytestmark = pytest.mark.no_cleanup_check_rabbitmq_server_has_no_errors


@pytest.fixture
def rabbit_settings() -> RabbitSettings:
    return RabbitSettings.model_construct(
        RABBIT_HOST="localhost",
        RABBIT_PORT=5672,
        RABBIT_USER="guest",
        RABBIT_PASSWORD=MagicMock(get_secret_value=lambda: "guest"),
    )


@pytest.fixture
def client_base(rabbit_settings: RabbitSettings) -> RabbitMQClientBase:
    # RabbitMQClientBase is abstract; create the minimal concrete subclass inline
    class _Concrete(RabbitMQClientBase):
        async def close(self) -> None:
            pass

    # grace_period_s=0 so these tests observe the raw state transition immediately
    return _Concrete(client_name="test-client", settings=rabbit_settings, grace_period_s=0)


# ---------------------------------------------------------------------------
# _channel_close_callback
# ---------------------------------------------------------------------------


def test_channel_close_callback_with_connection_closed_marks_unhealthy(
    client_base: RabbitMQClientBase,
):
    """When the broker forces connection closure (AWS MQ maintenance, AMQP 320
    CONNECTION_FORCED), _channel_close_callback receives a ConnectionClosed
    exception. Any close marks the client unhealthy immediately; the
    grace period (not exercised here, grace_period_s=0) is what tolerates
    brief, self-healing reconnects handled by aio_pika's RobustConnection."""
    # Create a mock with __str__ method that includes the maintenance mode message
    reply_text = "CONNECTION_FORCED - Node was put into maintenance mode"
    mock_reply = MagicMock(reply_code=320, reply_text=reply_text)
    mock_reply.__str__.return_value = reply_text
    exc = aiormq.exceptions.ConnectionClosed(mock_reply)
    client_base._channel_close_callback(sender="1", exc=exc)
    assert client_base.healthy is False


def test_channel_close_callback_with_cancelled_error_marks_unhealthy(
    client_base: RabbitMQClientBase,
):
    """asyncio.CancelledError during shutdown still marks the client unhealthy."""
    client_base._channel_close_callback(sender="1", exc=asyncio.CancelledError())
    assert client_base.healthy is False


def test_channel_close_callback_with_channel_closed_marks_unhealthy(
    client_base: RabbitMQClientBase,
):
    """A normal ChannelClosed (e.g. consumer cancel) marks the client unhealthy."""
    exc = aiormq.exceptions.ChannelClosed(MagicMock(reply_code=404, reply_text="NOT_FOUND"))
    client_base._channel_close_callback(sender="1", exc=exc)
    assert client_base.healthy is False


def test_channel_close_callback_with_unexpected_error_marks_unhealthy(
    client_base: RabbitMQClientBase,
):
    """An unrecognised exception in the channel close callback must mark the
    client unhealthy — this is the regression guard."""
    client_base._channel_close_callback(sender="1", exc=RuntimeError("something truly unexpected"))
    assert client_base.healthy is False


def test_channel_close_callback_with_no_exception_stays_healthy(
    client_base: RabbitMQClientBase,
):
    """Callback called with exc=None (clean close) must not affect health."""
    client_base._channel_close_callback(sender="1", exc=None)
    assert client_base.healthy is True


# ---------------------------------------------------------------------------
# _connection_close_callback — regression guard (already correct)
# ---------------------------------------------------------------------------


def test_connection_close_callback_with_cancelled_error_marks_unhealthy(
    client_base: RabbitMQClientBase,
):
    client_base._connection_close_callback(sender="1", exc=asyncio.CancelledError())
    assert client_base.healthy is False


def test_connection_close_callback_with_connection_closed_marks_unhealthy(
    client_base: RabbitMQClientBase,
):
    mock_reply = MagicMock(reply_code=320, reply_text="CONNECTION_FORCED - Node was put into maintenance mode")
    mock_reply.__str__.return_value = "CONNECTION_FORCED - Node was put into maintenance mode"
    exc = aiormq.exceptions.ConnectionClosed(mock_reply)
    client_base._connection_close_callback(sender="1", exc=exc)
    assert client_base.healthy is False


def test_connection_close_callback_with_unexpected_error_marks_unhealthy(
    client_base: RabbitMQClientBase,
):
    client_base._connection_close_callback(sender="1", exc=RuntimeError("unexpected"))
    assert client_base.healthy is False


# ---------------------------------------------------------------------------
# _connection_reconnect_callback — recovery guard
# ---------------------------------------------------------------------------


def test_connection_reconnect_callback_restores_healthy_state(
    client_base: RabbitMQClientBase,
):
    """After a transient broker disruption flips the client to unhealthy, a
    successful (re)connection must restore the healthy state. Without this the
    `_healthy_state` latch stays False forever and the liveness probe keeps
    restarting the service."""
    client_base._connection_close_callback(sender="1", exc=RuntimeError("unexpected"))
    assert client_base.healthy is False

    client_base._connection_reconnect_callback()
    assert client_base.healthy is True


# ---------------------------------------------------------------------------
# grace period — tolerate brief, self-healing disconnects
# ---------------------------------------------------------------------------


@pytest.fixture
def client_base_with_grace_period(rabbit_settings: RabbitSettings) -> RabbitMQClientBase:
    class _Concrete(RabbitMQClientBase):
        async def close(self) -> None:
            pass

    return _Concrete(client_name="test-client", settings=rabbit_settings, grace_period_s=10)


def test_disconnect_within_grace_period_stays_healthy(
    client_base_with_grace_period: RabbitMQClientBase,
    monkeypatch: pytest.MonkeyPatch,
):
    """A disconnect must not be surfaced as unhealthy until it outlasts the
    grace period, so brief AWS MQ maintenance blips don't trigger restarts."""
    fake_now = 1_000.0
    monkeypatch.setattr("servicelib.rabbitmq._client_base.time.monotonic", lambda: fake_now)

    client_base_with_grace_period._connection_close_callback(sender="1", exc=RuntimeError("unexpected"))
    assert client_base_with_grace_period.healthy is True

    fake_now += 5  # still within the 10s grace period
    assert client_base_with_grace_period.healthy is True


def test_disconnect_beyond_grace_period_becomes_unhealthy(
    client_base_with_grace_period: RabbitMQClientBase,
    monkeypatch: pytest.MonkeyPatch,
):
    """Once the disconnect outlasts the grace period, healthy must report False."""
    fake_now = 1_000.0
    monkeypatch.setattr("servicelib.rabbitmq._client_base.time.monotonic", lambda: fake_now)

    client_base_with_grace_period._connection_close_callback(sender="1", exc=RuntimeError("unexpected"))
    assert client_base_with_grace_period.healthy is True

    fake_now += 11  # beyond the 10s grace period
    assert client_base_with_grace_period.healthy is False


def test_reconnect_within_grace_period_resets_timer(
    client_base_with_grace_period: RabbitMQClientBase,
    monkeypatch: pytest.MonkeyPatch,
):
    """A successful reconnect clears the disconnect timer, so a later
    disconnect starts its own grace period rather than reusing a stale one."""
    fake_now = 1_000.0
    monkeypatch.setattr("servicelib.rabbitmq._client_base.time.monotonic", lambda: fake_now)

    client_base_with_grace_period._connection_close_callback(sender="1", exc=RuntimeError("unexpected"))
    fake_now += 5
    client_base_with_grace_period._connection_reconnect_callback()
    assert client_base_with_grace_period.healthy is True

    fake_now += 8  # would have exceeded the original grace window, but the timer was reset
    client_base_with_grace_period._connection_close_callback(sender="1", exc=RuntimeError("unexpected"))
    assert client_base_with_grace_period.healthy is True
