# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import logging
import os
import socket
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

import aio_pika
import pytest
import tenacity
from models_library.rabbitmq_messages import (
    EventRabbitMessage,
    InstrumentationRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessage,
)
from settings_library.rabbit import RabbitSettings
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from .helpers.utils_docker import get_localhost_ip, get_service_published_port

log = logging.getLogger(__name__)


@tenacity.retry(
    wait=wait_fixed(5),
    stop=stop_after_attempt(60),
    before_sleep=before_sleep_log(log, logging.INFO),
    reraise=True,
)
async def wait_till_rabbit_responsive(url: str) -> None:
    connection = await aio_pika.connect(url)
    await connection.close()


@pytest.fixture(scope="function")
async def rabbit_settings(
    docker_stack: dict, testing_environ_vars: dict  # stack is up
) -> RabbitSettings:
    """Returns the settings of a rabbit service that is up and responsive"""

    prefix = testing_environ_vars["SWARM_STACK_NAME"]
    assert f"{prefix}_rabbit" in docker_stack["services"]

    port = get_service_published_port("rabbit", testing_environ_vars["RABBIT_PORT"])

    settings = RabbitSettings(
        RABBIT_USER=testing_environ_vars["RABBIT_USER"],
        RABBIT_PASSWORD=testing_environ_vars["RABBIT_PASSWORD"],
        RABBIT_HOST=get_localhost_ip(),
        RABBIT_PORT=int(port),
    )

    await wait_till_rabbit_responsive(settings.dsn)

    return settings


@pytest.fixture(scope="function")
async def rabbit_service(
    rabbit_settings: RabbitSettings, monkeypatch: pytest.MonkeyPatch
) -> RabbitSettings:
    """Sets env vars for a rabbit service is up and responsive and returns its settings as well

    NOTE: Use this fixture to setup client app
    """
    monkeypatch.setenv("RABBIT_HOST", rabbit_settings.RABBIT_HOST)
    monkeypatch.setenv("RABBIT_PORT", str(rabbit_settings.RABBIT_PORT))
    monkeypatch.setenv("RABBIT_USER", rabbit_settings.RABBIT_USER)
    monkeypatch.setenv(
        "RABBIT_PASSWORD", rabbit_settings.RABBIT_PASSWORD.get_secret_value()
    )

    return rabbit_settings


@pytest.fixture(scope="function")
async def rabbit_connection(
    rabbit_settings: RabbitSettings,
) -> AsyncIterator[aio_pika.abc.AbstractConnection]:
    def _reconnect_callback():
        pytest.fail("rabbit reconnected")

    def _connection_close_callback(sender: Any, exc: Optional[BaseException] = None):
        if exc and not isinstance(exc, asyncio.CancelledError):
            pytest.fail(f"rabbit connection closed with exception {exc} from {sender}!")
        print("<-- connection closed")

    # create connection
    # NOTE: to show the connection name in the rabbitMQ UI see there
    # https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url
    connection = await aio_pika.connect_robust(
        rabbit_settings.dsn + f"?name={__name__}_{socket.gethostname()}_{os.getpid()}",
        client_properties={"connection_name": "pytest read connection"},
    )
    assert connection
    assert not connection.is_closed
    connection.reconnect_callbacks.add(_reconnect_callback)
    connection.close_callbacks.add(_connection_close_callback)

    yield connection
    # close connection
    await connection.close()
    assert connection.is_closed


@pytest.fixture(scope="function")
async def rabbit_channel(
    rabbit_connection: aio_pika.abc.AbstractConnection,
) -> AsyncIterator[aio_pika.abc.AbstractChannel]:
    def _channel_close_callback(sender: Any, exc: Optional[BaseException] = None):
        if exc and not isinstance(exc, asyncio.CancelledError):
            pytest.fail(f"rabbit channel closed with exception {exc} from {sender}!")
        print("<-- rabbit channel closed")

    # create channel
    async with rabbit_connection.channel() as channel:
        print("--> rabbit channel created")
        channel.close_callbacks.add(_channel_close_callback)
        yield channel
    assert channel.is_closed


@dataclass
class RabbitExchanges:
    logs: aio_pika.abc.AbstractExchange
    progress: aio_pika.abc.AbstractExchange
    instrumentation: aio_pika.abc.AbstractExchange
    events: aio_pika.abc.AbstractExchange


@pytest.fixture(scope="function")
async def rabbit_exchanges(
    rabbit_settings: RabbitSettings,
    rabbit_channel: aio_pika.Channel,
) -> RabbitExchanges:

    # declare log exchange
    logs_exchange = await rabbit_channel.declare_exchange(
        LoggerRabbitMessage.get_channel_name(),
        aio_pika.ExchangeType.FANOUT,
        durable=True,
    )
    assert logs_exchange

    # declare progress exchange
    progress_exchange = await rabbit_channel.declare_exchange(
        ProgressRabbitMessage.get_channel_name(),
        aio_pika.ExchangeType.FANOUT,
        durable=True,
    )
    assert progress_exchange

    # declare instrumentation exchange
    instrumentation_exchange = await rabbit_channel.declare_exchange(
        InstrumentationRabbitMessage.get_channel_name(),
        aio_pika.ExchangeType.FANOUT,
        durable=True,
    )
    assert instrumentation_exchange

    # declare instrumentation exchange
    events_exchange = await rabbit_channel.declare_exchange(
        EventRabbitMessage.get_channel_name(),
        aio_pika.ExchangeType.FANOUT,
        durable=True,
    )
    assert instrumentation_exchange

    return RabbitExchanges(
        logs_exchange, progress_exchange, instrumentation_exchange, events_exchange
    )


@pytest.fixture(scope="function")
async def rabbit_queue(
    rabbit_channel: aio_pika.Channel,
    rabbit_exchanges: RabbitExchanges,
) -> AsyncIterator[aio_pika.abc.AbstractQueue]:
    queue = await rabbit_channel.declare_queue(exclusive=True)
    assert queue

    # Binding queue to exchange
    await queue.bind(rabbit_exchanges.logs)
    await queue.bind(rabbit_exchanges.progress)
    await queue.bind(rabbit_exchanges.instrumentation)
    yield queue
    # unbind
    await queue.unbind(rabbit_exchanges.logs)
    await queue.unbind(rabbit_exchanges.progress)
    await queue.unbind(rabbit_exchanges.instrumentation)
