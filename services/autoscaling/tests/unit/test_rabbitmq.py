# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
from typing import Any, Mapping

import aiodocker
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.rabbitmq_messages import (
    AutoscalingStatus,
    LoggerRabbitMessage,
    RabbitAutoscalingMessage,
    RabbitMessageBase,
)
from pytest_mock.plugin import MockerFixture
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings
from simcore_service_autoscaling.core.errors import ConfigurationError
from simcore_service_autoscaling.modules.rabbitmq import (
    get_rabbitmq_client,
    post_message,
)
from tenacity import retry
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_TENACITY_RETRY_PARAMS = dict(
    reraise=True,
    retry=retry_if_exception_type(AssertionError),
    stop=stop_after_delay(30),
    wait=wait_fixed(0.5),
)

# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


@pytest.fixture
def rabbit_autoscaling_message(faker: Faker) -> RabbitAutoscalingMessage:
    return RabbitAutoscalingMessage(
        origin=faker.pystr(),
        number_monitored_nodes=faker.pyint(),
        cluster_total_resources=faker.pydict(),
        cluster_used_resources=faker.pydict(),
        number_pending_tasks_without_resources=faker.pyint(),
        status=AutoscalingStatus.IDLE,
    )


@pytest.fixture
def rabbit_log_message(faker: Faker) -> LoggerRabbitMessage:
    return LoggerRabbitMessage(
        user_id=faker.pyint(min_value=1),
        project_id=faker.uuid4(),
        node_id=faker.uuid4(),
        messages=faker.pylist(allowed_types=(str,)),
    )


@pytest.fixture(params=["rabbit_autoscaling_message", "rabbit_log_message"])
def rabbit_message(
    request: pytest.FixtureRequest,
    rabbit_autoscaling_message: RabbitAutoscalingMessage,
    rabbit_log_message: LoggerRabbitMessage,
) -> RabbitMessageBase:
    return {
        "rabbit_autoscaling_message": rabbit_autoscaling_message,
        "rabbit_log_message": rabbit_log_message,
    }[request.param]


def test_rabbitmq_does_not_initialize_if_deactivated(
    disabled_rabbitmq: None, disabled_ec2: None, initialized_app: FastAPI
):
    assert hasattr(initialized_app.state, "rabbitmq_client")
    assert initialized_app.state.rabbitmq_client == None
    with pytest.raises(ConfigurationError):
        get_rabbitmq_client(initialized_app)


def test_rabbitmq_initializes(
    enabled_rabbitmq: RabbitSettings, disabled_ec2: None, initialized_app: FastAPI
):
    assert hasattr(initialized_app.state, "rabbitmq_client")
    assert initialized_app.state.rabbitmq_client is not None
    assert get_rabbitmq_client(initialized_app) == initialized_app.state.rabbitmq_client


async def test_post_message(
    disable_dynamic_service_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    initialized_app: FastAPI,
    rabbit_message: RabbitMessageBase,
    rabbit_client: RabbitMQClient,
    mocker: MockerFixture,
):
    mocked_message_handler = mocker.AsyncMock(return_value=True)
    await rabbit_client.subscribe(rabbit_message.channel_name, mocked_message_handler)
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
    initialized_app: FastAPI,
    rabbit_message: RabbitMessageBase,
):
    await post_message(initialized_app, message=rabbit_message)


async def _switch_off_rabbit_mq_instance(async_docker_client: aiodocker.Docker) -> None:
    # remove the rabbit MQ instance
    rabbit_services = [
        s
        for s in await async_docker_client.services.list()
        if "rabbit" in s["Spec"]["Name"]
    ]
    await asyncio.gather(
        *(async_docker_client.services.delete(s["ID"]) for s in rabbit_services)
    )

    @retry(**_TENACITY_RETRY_PARAMS)
    async def _check_service_task_gone(service: Mapping[str, Any]) -> None:
        print(
            f"--> checking if service {service['ID']}:{service['Spec']['Name']} is really gone..."
        )
        list_of_tasks = await async_docker_client.containers.list(
            all=True,
            filters={
                "label": [f"com.docker.swarm.service.id={service['ID']}"],
            },
        )
        assert not list_of_tasks
        print(f"<-- service {service['ID']}:{service['Spec']['Name']} is gone.")

    await asyncio.gather(*(_check_service_task_gone(s) for s in rabbit_services))


async def test_post_message_when_rabbit_disconnected(
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    initialized_app: FastAPI,
    rabbit_autoscaling_message: RabbitAutoscalingMessage,
    async_docker_client: aiodocker.Docker,
):
    await _switch_off_rabbit_mq_instance(async_docker_client)

    # now posting should not raise out
    await post_message(initialized_app, message=rabbit_autoscaling_message)
