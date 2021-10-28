# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
import asyncio
import json
from asyncio import AbstractEventLoop
from pprint import pformat
from typing import Iterator, List
from uuid import uuid4

import aio_pika
import pytest
from _pytest.fixtures import FixtureRequest
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.settings.rabbit import RabbitConfig
from models_library.users import UserID
from pytest_mock.plugin import MockerFixture
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_sidecar.core.rabbitmq import RabbitMQ

pytestmark = pytest.mark.asyncio


pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.tmp_path_extra",
]

pytest_simcore_core_services_selection = ["rabbit"]

# FIXTURE


@pytest.yield_fixture(scope="module")
def event_loop(request: FixtureRequest) -> Iterator[AbstractEventLoop]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def setup(event_loop: AbstractEventLoop, rabbit_service: RabbitConfig) -> None:
    pass


@pytest.fixture
def user_id() -> UserID:
    return 1


@pytest.fixture
def project_id() -> ProjectID:
    return uuid4()


@pytest.fixture
def node_id() -> NodeID:
    return uuid4()


# TESTS


async def test_rabbitmq(
    setup: None,
    rabbit_queue: aio_pika.Queue,
    mocker: MockerFixture,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
):
    rabbit = RabbitMQ(rabbit_settings=RabbitSettings())
    assert rabbit

    mock_close_connection_cb = mocker.patch(
        "simcore_service_dynamic_sidecar.core.rabbitmq._close_callback"
    )
    mock_close_channel_cb = mocker.patch(
        "simcore_service_dynamic_sidecar.core.rabbitmq._channel_close_callback"
    )

    log_msg: str = "I am logging"
    log_messages: List[str] = ["I", "am a logger", "man..."]

    incoming_data = []

    async def rabbit_message_handler(message: aio_pika.IncomingMessage):
        data = json.loads(message.body)
        incoming_data.append(data)

    await rabbit_queue.consume(rabbit_message_handler, exclusive=True, no_ack=True)

    await rabbit.connect()
    assert rabbit._connection.ready  # pylint: disable=protected-access

    await rabbit.post_log_message(user_id, project_id, node_id, log_msg)
    await rabbit.post_log_message(user_id, project_id, node_id, log_messages)

    await rabbit.close()

    # wait for all the messages to be delivered,
    # the next assert sometimes fails in the CI
    await asyncio.sleep(1)

    mock_close_channel_cb.assert_called_once()
    mock_close_connection_cb.assert_called_once()

    # if this fails the above sleep did not work
    assert len(incoming_data) == 2, f"missing incoming data: {pformat(incoming_data)}"

    assert incoming_data[0] == {
        "Channel": "Log",
        "Messages": [log_msg],
        "Node": f"{node_id}",
        "project_id": f"{project_id}",
        "user_id": f"{user_id}",
    }
    assert incoming_data[1] == {
        "Channel": "Log",
        "Messages": log_messages,
        "Node": f"{node_id}",
        "project_id": f"{project_id}",
        "user_id": f"{user_id}",
    }
