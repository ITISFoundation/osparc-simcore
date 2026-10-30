# pylint:disable=too-many-arguments
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.rabbitmq_messages import (
    LoggerRabbitMessage,
    RabbitAutoscalingStatusMessage,
    RabbitMessageBase,
)
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_mock.plugin import MockerFixture
from servicelib.rabbitmq import BIND_TO_ALL_TOPICS, RabbitMQClient
from settings_library.rabbit import RabbitSettings
from simcore_service_autoscaling.core.errors import ConfigurationError
from simcore_service_autoscaling.modules.rabbitmq import (
    get_rabbitmq_client,
    post_message,
)
from tenacity.asyncio import AsyncRetrying
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
def rabbit_autoscaling_message(faker: Faker) -> RabbitAutoscalingStatusMessage:
    return RabbitAutoscalingStatusMessage(
        origin=faker.pystr(),
        nodes_total=faker.pyint(),
        nodes_active=faker.pyint(),
        nodes_drained=faker.pyint(),
        cluster_total_resources=faker.pydict(),
        cluster_used_resources=faker.pydict(),
        instances_pending=faker.pyint(),
        instances_running=faker.pyint(),
    )


@pytest.fixture
def rabbit_log_message(faker: Faker) -> LoggerRabbitMessage:
    return LoggerRabbitMessage(
        user_id=TypeAdapter(UserID).validate_python(faker.pyint(min_value=1)),
        project_id=faker.uuid4(cast_to=None),  # type: ignore
        node_id=faker.uuid4(cast_to=None),  # type: ignore
        messages=faker.pylist(allowed_types=(str,)),
    )


@pytest.fixture(params=["rabbit_autoscaling_message", "rabbit_log_message"])
def rabbit_message(
    request: pytest.FixtureRequest,
    rabbit_autoscaling_message: RabbitAutoscalingStatusMessage,
    rabbit_log_message: LoggerRabbitMessage,
) -> RabbitMessageBase:
    return {
        "rabbit_autoscaling_message": rabbit_autoscaling_message,
        "rabbit_log_message": rabbit_log_message,
    }[request.param]


def test_rabbitmq_does_not_initialize_if_deactivated(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
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
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    assert hasattr(initialized_app.state, "rabbitmq_client")
    assert initialized_app.state.rabbitmq_client is not None
    assert get_rabbitmq_client(initialized_app) == initialized_app.state.rabbitmq_client


async def test_post_message(
    disable_autoscaling_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    rabbit_message: RabbitMessageBase,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    wait_till_queue_has_consumer: Callable[[str, str], Awaitable[None]],
    wait_till_rabbit_client_is_connected: Callable[[RabbitMQClient], Awaitable[None]],
    mocker: MockerFixture,
):
    mocked_message_handler = mocker.AsyncMock(return_value=True)
    client = create_rabbitmq_client("pytest_consumer")
    queue_name, _ = await client.subscribe(
        rabbit_message.channel_name,
        mocked_message_handler,
        topics=[BIND_TO_ALL_TOPICS] if rabbit_message.routing_key() else None,
    )
    await wait_till_queue_has_consumer(queue_name, enabled_rabbitmq.RABBIT_VHOST)
    await wait_till_rabbit_client_is_connected(get_rabbitmq_client(initialized_app))
    await post_message(initialized_app, message=rabbit_message)

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            print(
                f"--> checking for message in rabbit exchange {rabbit_message.channel_name}, "
                f"{attempt.retry_state.retry_object.statistics}"
            )
            mocked_message_handler.assert_called_once_with(rabbit_message.model_dump_json().encode())
            print("... message received")


async def test_post_message_with_disabled_rabbit_does_not_raise(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    rabbit_message: RabbitMessageBase,
):
    await post_message(initialized_app, message=rabbit_message)


@pytest.mark.docker_exclusive(
    reason="pauses the 'rabbit' container of the docker stack shared by all xdist workers, "
    "freezing the broker the other workers' apps are connected to",
)
async def test_post_message_when_rabbit_disconnected(
    paused_container: Callable[[str], AbstractAsyncContextManager[None]],
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    rabbit_autoscaling_message: RabbitAutoscalingStatusMessage,
):
    await post_message(initialized_app, message=rabbit_autoscaling_message)
    async with paused_container("rabbit"):
        # now posting should not raise out
        await post_message(initialized_app, message=rabbit_autoscaling_message)
