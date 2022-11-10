# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from pprint import pformat

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
from simcore_service_dynamic_sidecar.core.rabbitmq import RabbitMQ

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

    rabbit = app.state.rabbitmq
    assert isinstance(rabbit, RabbitMQ)

    incoming_data: list[LoggerRabbitMessage] = []

    async def rabbit_message_handler(
        message: aio_pika.abc.AbstractIncomingMessage,
    ) -> None:
        incoming_data.append(LoggerRabbitMessage.parse_raw(message.body))

    await rabbit_queue.consume(rabbit_message_handler, exclusive=True, no_ack=True)

    assert rabbit._connection
    assert rabbit._connection.ready

    log_msg: str = "I am logging"
    log_messages: list[str] = ["I", "am a logger", "man..."]
    log_more_messages: list[str] = [f"msg{1}" for i in range(10)]

    await rabbit.post_log_message(log_msg)
    await rabbit.post_log_message(log_messages)

    # make sure the first 2 messages are
    # sent in the same chunk
    await rabbit.post_log_message(log_more_messages)
    # wait for all the messages to be delivered,
    # need to make sure all messages are delivered
    await asyncio.sleep(1.1)

    # if this fails the above sleep did not work
    assert len(incoming_data) == 2, f"missing incoming data: {pformat(incoming_data)}"
    assert incoming_data[0] == LoggerRabbitMessage(
        messages=[log_msg] + log_messages,
        node_id=node_id,
        project_id=project_id,
        user_id=user_id,
    )

    assert incoming_data[1] == LoggerRabbitMessage(
        messages=log_more_messages,
        node_id=node_id,
        project_id=project_id,
        user_id=user_id,
    )

    # ensure closes correctly
    await rabbit.close()
