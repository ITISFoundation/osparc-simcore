# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio

import aio_pika
import pytest
from async_asgi_testclient import TestClient
from fastapi.applications import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.users import UserID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_sidecar.core.application import create_app
from simcore_service_dynamic_sidecar.core.rabbitmq import (
    RabbitMQClient,
    get_rabbitmq_client,
    post_log_message,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def app(
    rabbit_service: RabbitSettings, docker_registry: str, mock_environment: EnvVarsDict
) -> FastAPI:
    """app w/o mocking registry or rabbit"""
    return create_app()


async def test_rabbitmq(
    rabbit_queue: aio_pika.abc.AbstractQueue,
    mocker: MockerFixture,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    test_client: TestClient,
):
    app = test_client.application
    assert isinstance(app, FastAPI)

    rabbit = get_rabbitmq_client(app)
    assert isinstance(rabbit, RabbitMQClient)

    incoming_data: list[LoggerRabbitMessage] = []

    async def rabbit_message_handler(
        message: aio_pika.abc.AbstractIncomingMessage,
    ) -> None:
        incoming_data.append(LoggerRabbitMessage.parse_raw(message.body))

    await rabbit_queue.consume(rabbit_message_handler, exclusive=True)

    log_msg_in_a_str: str = "I am logging"
    log_messages_in_array: list[str] = ["I", "am a logger", "man..."]

    await post_log_message(app, log_msg_in_a_str)
    await post_log_message(app, log_messages_in_array)
    await asyncio.sleep(3.1)
    # we have now 2 messages in the queue
    assert len(incoming_data) == 2
    assert incoming_data[0] == LoggerRabbitMessage(
        messages=[log_msg_in_a_str],
        node_id=node_id,
        project_id=project_id,
        user_id=user_id,
    )

    assert incoming_data[1] == LoggerRabbitMessage(
        messages=log_messages_in_array,
        node_id=node_id,
        project_id=project_id,
        user_id=user_id,
    )
