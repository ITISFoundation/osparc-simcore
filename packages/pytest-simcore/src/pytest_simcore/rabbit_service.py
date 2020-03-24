# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
from typing import Dict, Tuple, Optional

import aio_pika
import pytest
import tenacity

from servicelib.rabbitmq_utils import RabbitMQRetryPolicyUponInitialization
from simcore_sdk.config.rabbit import Config
from .helpers.utils_docker import get_service_published_port


@pytest.fixture(scope="module")
def rabbit_config(docker_stack: Dict, devel_environ: Dict) -> Dict:
    assert "simcore_rabbit" in docker_stack["services"]

    config = {
        "host": "127.0.0.1",
        "port": get_service_published_port("rabbit", devel_environ["RABBIT_PORT"]),
        "user": devel_environ["RABBIT_USER"],
        "password": devel_environ["RABBIT_PASSWORD"],
    }

    # sidecar takes its configuration from env variables
    os.environ["RABBIT_HOST"] = "127.0.0.1"
    os.environ["RABBIT_PORT"] = config["port"]
    os.environ["RABBIT_USER"] = devel_environ["RABBIT_USER"]
    os.environ["RABBIT_PASSWORD"] = devel_environ["RABBIT_PASSWORD"]
    os.environ["RABBIT_CHANNELS"] = devel_environ["RABBIT_CHANNELS"]

    yield config


@pytest.fixture(scope="function")
async def rabbit_service(rabbit_config: Dict, docker_stack: Dict) -> str:
    url = "amqp://{user}:{password}@{host}:{port}".format(**rabbit_config)
    await wait_till_rabbit_responsive(url)
    yield url


@pytest.fixture(scope="function")
async def rabbit_connection(rabbit_service: str) -> aio_pika.RobustConnection:
    def reconnect_callback():
        pytest.fail("rabbit reconnected")

    # create connection
    connection = await aio_pika.connect_robust(
        rabbit_service, client_properties={"connection_name": "pytest read connection"}
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
    def channel_close_callback(exc: Optional[BaseException]):
        if exc:
            pytest.fail("rabbit channel closed!")

    # create channel
    channel = await rabbit_connection.channel()
    assert channel
    channel.add_close_callback(channel_close_callback)
    yield channel
    # close channel
    await channel.close()


@pytest.fixture(scope="function")
async def rabbit_exchange(
    rabbit_channel: aio_pika.Channel,
) -> Tuple[aio_pika.Exchange, aio_pika.Exchange]:
    rb_config = Config()

    # declare log exchange
    LOG_EXCHANGE_NAME: str = rb_config.channels["log"]
    logs_exchange = await rabbit_channel.declare_exchange(
        LOG_EXCHANGE_NAME, aio_pika.ExchangeType.FANOUT
    )
    # declare progress exchange
    PROGRESS_EXCHANGE_NAME: str = rb_config.channels["progress"]
    progress_exchange = await rabbit_channel.declare_exchange(
        PROGRESS_EXCHANGE_NAME, aio_pika.ExchangeType.FANOUT
    )

    yield logs_exchange, progress_exchange


@pytest.fixture(scope="function")
async def rabbit_queue(
    rabbit_channel: aio_pika.Channel,
    rabbit_exchange: Tuple[aio_pika.Exchange, aio_pika.Exchange],
) -> aio_pika.Queue:
    (logs_exchange, progress_exchange) = rabbit_exchange
    # declare queue
    queue = await rabbit_channel.declare_queue(exclusive=True)
    # Binding queue to exchange
    await queue.bind(logs_exchange)
    await queue.bind(progress_exchange)
    yield queue


# HELPERS --


@tenacity.retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def wait_till_rabbit_responsive(url: str) -> None:
    connection = await aio_pika.connect(url)
    await connection.close()
