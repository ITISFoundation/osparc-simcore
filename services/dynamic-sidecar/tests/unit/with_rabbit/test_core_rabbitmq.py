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
from pytest import MonkeyPatch
from pytest_mock.plugin import MockerFixture
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_sidecar.core.application import create_app
from simcore_service_dynamic_sidecar.core.rabbitmq import SLEEP_BETWEEN_SENDS, RabbitMQ

pytest_simcore_core_services_selection = [
    "rabbit",
]

# FIXTURE


@pytest.fixture
def mock_environment(
    mock_environment: None,
    monkeypatch: MonkeyPatch,
    rabbit_service: RabbitSettings,
) -> None:

    # TODO: PC->ANE: this is already guaranteed in the pytest_simcore.rabbit_service fixture
    monkeypatch.setenv("RABBIT_HOST", rabbit_service.RABBIT_HOST)
    monkeypatch.setenv("RABBIT_PORT", f"{rabbit_service.RABBIT_PORT}")
    monkeypatch.setenv("RABBIT_USER", rabbit_service.RABBIT_USER)
    monkeypatch.setenv(
        "RABBIT_PASSWORD", rabbit_service.RABBIT_PASSWORD.get_secret_value()
    )
    # ---


@pytest.fixture
def app(mock_environment: None) -> FastAPI:
    """app w/o mocking registry or rabbit"""
    return create_app()


async def test_rabbitmq(
    rabbit_queue: aio_pika.Queue,
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

    mock_close_connection_cb = mocker.patch(
        "simcore_service_dynamic_sidecar.core.rabbitmq._close_callback"
    )
    mock_close_channel_cb = mocker.patch(
        "simcore_service_dynamic_sidecar.core.rabbitmq._channel_close_callback"
    )

    incoming_data: list[LoggerRabbitMessage] = []

    async def rabbit_message_handler(message: aio_pika.IncomingMessage):
        incoming_data.append(LoggerRabbitMessage.parse_raw(message.body))

    await rabbit_queue.consume(rabbit_message_handler, exclusive=True, no_ack=True)

    await rabbit.connect()
    assert rabbit._connection.ready  # pylint: disable=protected-access

    log_msg: str = "I am logging"
    log_messages: list[str] = ["I", "am a logger", "man..."]
    log_more_messages: list[str] = [f"msg{1}" for i in range(10)]

    await rabbit.post_log_message(log_msg)
    await rabbit.post_log_message(log_messages)

    # make sure the first 2 messages are
    # sent in the same chunk
    await asyncio.sleep(SLEEP_BETWEEN_SENDS * 1.1)
    await rabbit.post_log_message(log_more_messages)
    # wait for all the messages to be delivered,
    # need to make sure all messages are delivered
    await asyncio.sleep(SLEEP_BETWEEN_SENDS * 1.1)

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
    mock_close_connection_cb.assert_called_once()
    mock_close_channel_cb.assert_called_once()
