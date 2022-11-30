# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
from typing import Any, Mapping

import aiodocker
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.rabbitmq_messages import RabbitAutoscalingMessage
from settings_library.rabbit import RabbitSettings
from simcore_service_autoscaling.core.errors import ConfigurationError
from simcore_service_autoscaling.rabbitmq import (
    get_rabbitmq_client,
    post_cluster_state_message,
)
from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


def test_rabbitmq_does_not_initialize_if_deactivated(
    disabled_rabbitmq, initialized_app: FastAPI
):
    assert hasattr(initialized_app.state, "rabbitmq_client")
    assert initialized_app.state.rabbitmq_client == None
    with pytest.raises(ConfigurationError):
        get_rabbitmq_client(initialized_app)


def test_rabbitmq_initializes(
    enabled_rabbitmq: RabbitSettings, initialized_app: FastAPI
):
    assert hasattr(initialized_app.state, "rabbitmq_client")
    assert initialized_app.state.rabbitmq_client is not None
    assert get_rabbitmq_client(initialized_app) == initialized_app.state.rabbitmq_client


@pytest.fixture
def rabbit_autoscaling_message(faker: Faker) -> RabbitAutoscalingMessage:
    return RabbitAutoscalingMessage(
        origin=faker.pystr(),
        number_monitored_nodes=faker.pyint(),
        cluster_total_resources=faker.pydict(),
        cluster_used_resources=faker.pydict(),
        number_pending_tasks_without_resources=faker.pyint(),
    )


async def test_post_cluster_state_message(
    enabled_rabbitmq: RabbitSettings,
    initialized_app: FastAPI,
    rabbit_autoscaling_message: RabbitAutoscalingMessage,
):
    await post_cluster_state_message(
        initialized_app, state_msg=rabbit_autoscaling_message
    )


async def test_post_cluster_state_message_with_disabled_rabbit(
    disabled_rabbitmq: None,
    initialized_app: FastAPI,
    rabbit_autoscaling_message: RabbitAutoscalingMessage,
):
    await post_cluster_state_message(
        initialized_app, state_msg=rabbit_autoscaling_message
    )


async def test_post_cluster_state_message_when_rabbit_disconnected(
    enabled_rabbitmq: RabbitSettings,
    initialized_app: FastAPI,
    rabbit_autoscaling_message: RabbitAutoscalingMessage,
    async_docker_client: aiodocker.Docker,
):
    # remove the rabbit MQ instance
    rabbit_services = [
        s
        for s in await async_docker_client.services.list()
        if "rabbit" in s["Spec"]["Name"]
    ]
    await asyncio.gather(
        *(async_docker_client.services.delete(s["ID"]) for s in rabbit_services)
    )

    @retry(
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    )
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

    # now posting should not raise out
    await post_cluster_state_message(
        initialized_app, state_msg=rabbit_autoscaling_message
    )
