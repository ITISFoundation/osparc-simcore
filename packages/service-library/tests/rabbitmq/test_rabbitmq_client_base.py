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

    return _Concrete(client_name="test-client", settings=rabbit_settings)


# ---------------------------------------------------------------------------
# _channel_close_callback
# ---------------------------------------------------------------------------


def test_channel_close_callback_with_connection_closed_stays_healthy(
    client_base: RabbitMQClientBase,
):
    """When the broker forces connection closure (AWS MQ maintenance, AMQP 320
    CONNECTION_FORCED), _channel_close_callback receives a ConnectionClosed
    exception. This must NOT mark the client unhealthy — aio_pika's
    RobustConnection handles reconnection automatically."""
    exc = aiormq.exceptions.ConnectionClosed(
        MagicMock(reply_code=320, reply_text="CONNECTION_FORCED - Node was put into maintenance mode")
    )
    client_base._channel_close_callback(sender="1", exc=exc)
    assert client_base.healthy is True


def test_channel_close_callback_with_cancelled_error_stays_healthy(
    client_base: RabbitMQClientBase,
):
    """asyncio.CancelledError during shutdown must not mark the client unhealthy."""
    client_base._channel_close_callback(sender="1", exc=asyncio.CancelledError())
    assert client_base.healthy is True


def test_channel_close_callback_with_channel_closed_stays_healthy(
    client_base: RabbitMQClientBase,
):
    """A normal ChannelClosed (e.g. consumer cancel) must not mark the client unhealthy."""
    exc = aiormq.exceptions.ChannelClosed(MagicMock(reply_code=404, reply_text="NOT_FOUND"))
    client_base._channel_close_callback(sender="1", exc=exc)
    assert client_base.healthy is True


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


def test_connection_close_callback_with_connection_closed_stays_healthy(
    client_base: RabbitMQClientBase,
):
    exc = aiormq.exceptions.ConnectionClosed(
        MagicMock(reply_code=320, reply_text="CONNECTION_FORCED - Node was put into maintenance mode")
    )
    client_base._connection_close_callback(sender="1", exc=exc)
    assert client_base.healthy is True


def test_connection_close_callback_with_unexpected_error_marks_unhealthy(
    client_base: RabbitMQClientBase,
):
    client_base._connection_close_callback(sender="1", exc=RuntimeError("unexpected"))
    assert client_base.healthy is False
