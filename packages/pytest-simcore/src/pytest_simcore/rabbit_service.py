# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
import logging
import socket
from typing import Any, Dict, Iterable, Optional, Tuple

import aio_pika
import pytest
import tenacity
from models_library.settings.rabbit import RabbitConfig
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from .helpers.utils_docker import get_service_published_port

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def loop(request) -> asyncio.AbstractEventLoop:
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

    yield rabbit_config


@pytest.fixture(scope="function")
async def rabbit_service(rabbit_config: RabbitConfig, monkeypatch) -> RabbitConfig:
    monkeypatch.setenv("RABBIT_HOST", rabbit_config.host)
    monkeypatch.setenv("RABBIT_PORT", str(rabbit_config.port))
    monkeypatch.setenv("RABBIT_USER", rabbit_config.user)
    monkeypatch.setenv("RABBIT_PASSWORD", rabbit_config.password.get_secret_value())
    monkeypatch.setenv("RABBIT_CHANNELS", json.dumps(rabbit_config.channels))

    return rabbit_config


@pytest.fixture(scope="function")
async def rabbit_connection(rabbit_config: RabbitConfig) -> aio_pika.RobustConnection:
    def reconnect_callback():
        pytest.fail("rabbit reconnected")

    # create connection
    # NOTE: to show the connection name in the rabbitMQ UI see there
    # https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url
    connection = await aio_pika.connect_robust(
        rabbit_config.dsn + f"?name={__name__}_{id(socket.gethostname())}",
        client_properties={"connection_name": "pytest read connection"},
    )
    assert connection
    assert not connection.is_closed
    connection.add_reconnect_callback(reconnect_callback)

    yield connection
    # close connection
    await connection.close()
    assert connection.is_closed


@pytest.fixture(scope="function")
async def rabbit_channel(
    rabbit_connection: aio_pika.RobustConnection,
) -> aio_pika.Channel:
    def channel_close_callback(sender: Any, exc: Optional[BaseException] = None):
        if exc:
            pytest.fail("rabbit channel closed!")
        else:
            print("sender was '{sender}'")

    # create channel
    channel = await rabbit_connection.channel(publisher_confirms=False)
    assert channel
    channel.add_close_callback(channel_close_callback)
    yield channel
    # close channel
    await channel.close()


@pytest.fixture(scope="function")
async def rabbit_exchange(
    rabbit_config: RabbitConfig,
    rabbit_channel: aio_pika.Channel,
) -> Tuple[aio_pika.Exchange, aio_pika.Exchange]:

    # declare log exchange
    LOG_EXCHANGE_NAME: str = rabbit_config.channels["log"]
    logs_exchange = await rabbit_channel.declare_exchange(
        LOG_EXCHANGE_NAME, aio_pika.ExchangeType.FANOUT
    )
    assert logs_exchange
    # declare instrumentation exchange
    INSTRUMENTATION_EXCHANGE_NAME: str = rabbit_config.channels["instrumentation"]
    instrumentation_exchange = await rabbit_channel.declare_exchange(
        INSTRUMENTATION_EXCHANGE_NAME, aio_pika.ExchangeType.FANOUT
    )
    assert instrumentation_exchange
    return logs_exchange, instrumentation_exchange


@pytest.fixture(scope="function")
async def rabbit_queue(
    rabbit_channel: aio_pika.Channel,
    rabbit_exchange: Tuple[aio_pika.Exchange, aio_pika.Exchange],
) -> Iterable[aio_pika.Queue]:
    (logs_exchange, instrumentation_exchange) = rabbit_exchange
    # declare queue
    queue = await rabbit_channel.declare_queue(exclusive=True)
    assert queue
    # Binding queue to exchange
    await queue.bind(logs_exchange)
    await queue.bind(instrumentation_exchange)
    yield queue


# HELPERS --


@tenacity.retry(
    wait=wait_fixed(5),
    stop=stop_after_attempt(60),
    before_sleep=before_sleep_log(log, logging.INFO),
    reraise=True,
)
async def wait_till_rabbit_responsive(url: str) -> None:
    connection = await aio_pika.connect(url)
    await connection.close()
