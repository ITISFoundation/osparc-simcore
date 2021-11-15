# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
import asyncio
import json
from pprint import pformat
from typing import List

import aio_pika
import pytest
from models_library.settings.celery import CeleryConfig
from models_library.settings.rabbit import RabbitConfig
from simcore_service_sidecar import config
from simcore_service_sidecar.rabbitmq import RabbitMQ

pytest_simcore_core_services_selection = ["rabbit"]


@pytest.fixture
async def sidecar_config():
    config.CELERY_CONFIG = CeleryConfig.create_from_env()


async def test_rabbitmq(
    loop,
    rabbit_service: RabbitConfig,
    rabbit_queue: aio_pika.Queue,
    sidecar_config,
    mocker,
):
    rabbit = RabbitMQ()
    assert rabbit

    mock_close_connection_cb = mocker.patch(
        "simcore_service_sidecar.rabbitmq._close_callback"
    )
    mock_close_channel_cb = mocker.patch(
        "simcore_service_sidecar.rabbitmq._channel_close_callback"
    )

    user_id: str = "some user id"
    project_id: str = "some project id"
    node_id: str = "some node id"
    progress_msg: str = "I progressed a lot since last time"
    log_msg: str = "I am logging"
    log_messages: List[str] = ["I", "am a logger", "man..."]

    incoming_data = []

    async def rabbit_message_handler(message: aio_pika.IncomingMessage):
        data = json.loads(message.body)
        incoming_data.append(data)

    await rabbit_queue.consume(rabbit_message_handler, exclusive=True, no_ack=True)

    async with RabbitMQ() as rabbitmq:
        assert rabbitmq._connection.ready  # pylint: disable=protected-access

        await rabbitmq.post_log_message(user_id, project_id, node_id, log_msg)
        await rabbitmq.post_log_message(user_id, project_id, node_id, log_messages)
        await rabbitmq.post_progress_message(user_id, project_id, node_id, progress_msg)

    # wait for all the messages to be delivered,
    # the next assert sometimes fails in the CI
    await asyncio.sleep(1)

    mock_close_channel_cb.assert_called_once()
    mock_close_connection_cb.assert_called_once()

    # if this fails the above sleep did not work
    assert len(incoming_data) == 3, f"missing incoming data: {pformat(incoming_data)}"

    assert incoming_data[0] == {
        "channel": "logger",
        "messages": [log_msg],
        "node_id": node_id,
        "project_id": project_id,
        "user_id": user_id,
    }
    assert incoming_data[1] == {
        "channel": "logger",
        "messages": ["I", "am a logger", "man..."],
        "node_id": "some node id",
        "project_id": "some project id",
        "user_id": "some user id",
    }
    assert incoming_data[2] == {
        "channel": "progress",
        "node_id": "some node id",
        "progress": "I progressed a lot since last time",
        "project_id": "some project id",
        "user_id": "some user id",
    }
