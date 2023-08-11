# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable

import aiodocker
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.rabbitmq_messages import LoggerRabbitMessage, RabbitMessageBase
from pytest_mock.plugin import MockerFixture
from servicelib.rabbitmq import BIND_TO_ALL_TOPICS, RabbitMQClient
from settings_library.rabbit import RabbitSettings
from simcore_service_clusters_keeper.core.errors import ConfigurationError
from simcore_service_clusters_keeper.modules.rabbitmq import (
    get_rabbitmq_client,
    post_message,
)
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_TENACITY_RETRY_PARAMS = {
    "reraise": True,
    "retry": retry_if_exception_type(AssertionError),
    "stop": stop_after_delay(30),
    "wait": wait_fixed(0.1),
}

# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


@pytest.fixture
def rabbit_log_message(faker: Faker) -> LoggerRabbitMessage:
    return LoggerRabbitMessage(
        user_id=faker.pyint(min_value=1),
        project_id=faker.uuid4(),
        node_id=faker.uuid4(),
        messages=faker.pylist(allowed_types=(str,)),
    )


@pytest.fixture(params=["rabbit_log_message"])
def rabbit_message(
    request: pytest.FixtureRequest,
    rabbit_log_message: LoggerRabbitMessage,
) -> RabbitMessageBase:
    return {
        "rabbit_log_message": rabbit_log_message,
    }[request.param]


def test_rabbitmq_does_not_initialize_if_deactivated(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    assert hasattr(initialized_app.state, "rabbitmq_client")
    assert initialized_app.state.rabbitmq_client is None
    with pytest.raises(ConfigurationError):
        get_rabbitmq_client(initialized_app)


def test_rabbitmq_initializes(
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    assert hasattr(initialized_app.state, "rabbitmq_client")
    assert initialized_app.state.rabbitmq_client is not None
    assert get_rabbitmq_client(initialized_app) == initialized_app.state.rabbitmq_client


async def test_post_message(
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    rabbit_message: RabbitMessageBase,
    rabbitmq_client: Callable[[str], RabbitMQClient],
    mocker: MockerFixture,
):
    mocked_message_handler = mocker.AsyncMock(return_value=True)
    client = rabbitmq_client("pytest_consumer")
    await client.subscribe(
        rabbit_message.channel_name,
        mocked_message_handler,
        topics=[BIND_TO_ALL_TOPICS] if rabbit_message.routing_key() else None,
    )
    await post_message(initialized_app, message=rabbit_message)

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            print(
                f"--> checking for message in rabbit exchange {rabbit_message.channel_name}, {attempt.retry_state.retry_object.statistics}"
            )
            mocked_message_handler.assert_called_once_with(
                rabbit_message.json().encode()
            )
            print("... message received")


async def test_post_message_with_disabled_rabbit_does_not_raise(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    rabbit_message: RabbitMessageBase,
):
    await post_message(initialized_app, message=rabbit_message)


@contextlib.asynccontextmanager
async def paused_container(
    async_docker_client: aiodocker.Docker, container_name: str
) -> AsyncIterator[None]:
    containers = await async_docker_client.containers.list(
        filters={"name": [container_name]}
    )
    await asyncio.gather(*(c.pause() for c in containers))
    # refresh
    container_attrs = await asyncio.gather(*(c.show() for c in containers))
    for container_status in container_attrs:
        assert container_status["State"]["Status"] == "paused"

    yield

    await asyncio.gather(*(c.unpause() for c in containers))
    # refresh
    container_attrs = await asyncio.gather(*(c.show() for c in containers))
    for container_status in container_attrs:
        assert container_status["State"]["Status"] == "running"


async def test_post_message_when_rabbit_disconnected_does_not_raise(
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    rabbit_log_message: LoggerRabbitMessage,
    async_docker_client: aiodocker.Docker,
):
    # NOTE: if the connection is not initialized before pausing the container, then
    # this test hangs forever!!! This needs investigations!
    await post_message(initialized_app, message=rabbit_log_message)
    async with paused_container(async_docker_client, "rabbit"):
        # now posting should not raise out
        await post_message(initialized_app, message=rabbit_log_message)
