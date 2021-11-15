# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
import logging
import os
import socket
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Iterator, Optional

import aio_pika
import pytest
import tenacity
from models_library.settings.rabbit import RabbitConfig
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from .helpers.utils_docker import get_service_published_port

# HELPERS ------------------------------------------------------------------------------------

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


# FIXTURES ------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def loop(request) -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def rabbit_config(
    loop: asyncio.AbstractEventLoop, docker_stack: Dict, testing_environ_vars: Dict
) -> RabbitConfig:
    prefix = testing_environ_vars["SWARM_STACK_NAME"]
    assert f"{prefix}_rabbit" in docker_stack["services"]
    rabbit_config = RabbitConfig(
        user=testing_environ_vars["RABBIT_USER"],
        password=testing_environ_vars["RABBIT_PASSWORD"],
        host="127.0.0.1",
        port=get_service_published_port("rabbit", testing_environ_vars["RABBIT_PORT"]),
        channels=json.loads(testing_environ_vars["RABBIT_CHANNELS"]),
    )

    url = rabbit_config.dsn
    await wait_till_rabbit_responsive(url)

    return rabbit_config


@pytest.fixture(scope="function")
async def rabbit_service(rabbit_config: RabbitConfig, monkeypatch) -> RabbitConfig:
    monkeypatch.setenv("RABBIT_HOST", rabbit_config.host)
    monkeypatch.setenv("RABBIT_PORT", str(rabbit_config.port))
    monkeypatch.setenv("RABBIT_USER", rabbit_config.user)
    monkeypatch.setenv("RABBIT_PASSWORD", rabbit_config.password.get_secret_value())
    monkeypatch.setenv("RABBIT_CHANNELS", json.dumps(rabbit_config.channels))

    return rabbit_config


@pytest.fixture(scope="function")
async def rabbit_connection(
    rabbit_config: RabbitConfig,
) -> AsyncIterator[aio_pika.RobustConnection]:
    def _reconnect_callback():
        pytest.fail("rabbit reconnected")

    # create connection
    # NOTE: to show the connection name in the rabbitMQ UI see there
    # https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url
    connection = await aio_pika.connect_robust(
        rabbit_config.dsn + f"?name={__name__}_{socket.gethostname()}_{os.getpid()}",
        client_properties={"connection_name": "pytest read connection"},
    )
    assert connection
    assert not connection.is_closed
    connection.add_reconnect_callback(_reconnect_callback)

    yield connection
    # close connection
    await connection.close()
    assert connection.is_closed


@pytest.fixture(scope="function")
async def rabbit_channel(
    rabbit_connection: aio_pika.RobustConnection,
) -> AsyncIterator[aio_pika.Channel]:
    def _channel_close_callback(sender: Any, exc: Optional[BaseException] = None):
        if exc:
            pytest.fail("rabbit channel closed!")
        else:
            print("sender was '{sender}'")

    # create channel
    channel = await rabbit_connection.channel(publisher_confirms=False)
    assert channel
    channel.add_close_callback(_channel_close_callback)
    yield channel
    # close channel
    await channel.close()


@dataclass
class RabbitExchanges:
    logs: aio_pika.Exchange
    progress: aio_pika.Exchange
    instrumentation: aio_pika.Exchange


@pytest.fixture(scope="function")
async def rabbit_exchanges(
    rabbit_config: RabbitConfig,
    rabbit_channel: aio_pika.Channel,
) -> RabbitExchanges:
    """
    Declares and returns 'log' and 'instrumentation' exchange channels with rabbit
    """

    # declare log exchange
    LOG_EXCHANGE_NAME: str = rabbit_config.channels["log"]
    logs_exchange = await rabbit_channel.declare_exchange(
        LOG_EXCHANGE_NAME, aio_pika.ExchangeType.FANOUT
    )
    assert logs_exchange

    # declare progress exchange
    PROGRESS_EXCHANGE_NAME: str = rabbit_config.channels["progress"]
    progress_exchange = await rabbit_channel.declare_exchange(
        PROGRESS_EXCHANGE_NAME, aio_pika.ExchangeType.FANOUT
    )
    assert progress_exchange

    # declare instrumentation exchange
    INSTRUMENTATION_EXCHANGE_NAME: str = rabbit_config.channels["instrumentation"]
    instrumentation_exchange = await rabbit_channel.declare_exchange(
        INSTRUMENTATION_EXCHANGE_NAME, aio_pika.ExchangeType.FANOUT
    )
    assert instrumentation_exchange

    return RabbitExchanges(logs_exchange, progress_exchange, instrumentation_exchange)


@pytest.fixture(scope="function")
async def rabbit_queue(
    rabbit_channel: aio_pika.Channel,
    rabbit_exchanges: RabbitExchanges,
) -> AsyncIterator[aio_pika.Queue]:
    queue = await rabbit_channel.declare_queue(exclusive=True)
    assert queue

    # Binding queue to exchange
    await queue.bind(rabbit_exchanges.logs)
    await queue.bind(rabbit_exchanges.progress)
    await queue.bind(rabbit_exchanges.instrumentation)
    yield queue
