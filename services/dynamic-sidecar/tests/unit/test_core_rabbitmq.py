# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
import asyncio
import json
import os
import uuid
from asyncio import AbstractEventLoop
from pathlib import Path
from pprint import pformat
from typing import Iterator, List
from unittest import mock

import aio_pika
import pytest
from _pytest.fixtures import FixtureRequest
from fastapi.applications import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.settings.rabbit import RabbitConfig
from models_library.users import UserID
from pytest_mock.plugin import MockerFixture
from simcore_service_dynamic_sidecar.core.rabbitmq import RabbitMQ
from simcore_service_dynamic_sidecar.modules import mounted_fs

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


@pytest.fixture(scope="module")
def user_id() -> UserID:
    return 1


@pytest.fixture(scope="module")
def project_id() -> ProjectID:
    return uuid.uuid4()


@pytest.fixture(scope="module")
def node_id() -> NodeID:
    return uuid.uuid4()


@pytest.fixture(scope="module")
def mock_environment(
    event_loop: AbstractEventLoop,
    mock_dy_volumes: Path,
    compose_namespace: str,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: List[Path],
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> Iterator[None]:
    with mock.patch.dict(
        os.environ,
        {
            "SC_BOOT_MODE": "production",
            "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": compose_namespace,
            "REGISTRY_AUTH": "false",
            "REGISTRY_USER": "test",
            "REGISTRY_PW": "test",
            "REGISTRY_SSL": "false",
            "DY_SIDECAR_PATH_INPUTS": str(inputs_dir),
            "DY_SIDECAR_PATH_OUTPUTS": str(outputs_dir),
            "DY_SIDECAR_STATE_PATHS": json.dumps([str(x) for x in state_paths_dirs]),
            "DY_SIDECAR_USER_ID": f"{user_id}",
            "DY_SIDECAR_PROJECT_ID": f"{project_id}",
            "DY_SIDECAR_NODE_ID": f"{node_id}",
        },
    ), mock.patch.object(mounted_fs, "DY_VOLUMES", mock_dy_volumes):
        print(os.environ)
        yield


# UTILS


def _patch_settings_with_rabbit(app: FastAPI, rabbit_service: RabbitConfig) -> None:
    app.state.settings.RABBIT_SETTINGS.__config__.allow_mutation = True
    app.state.settings.RABBIT_SETTINGS.__config__.frozen = False

    app.state.settings.RABBIT_SETTINGS.RABBIT_HOST = rabbit_service.host
    app.state.settings.RABBIT_SETTINGS.RABBIT_PORT = rabbit_service.port
    app.state.settings.RABBIT_SETTINGS.RABBIT_USER = rabbit_service.user
    app.state.settings.RABBIT_SETTINGS.RABBIT_PASSWORD = rabbit_service.password


# TESTS


async def test_rabbitmq(
    rabbit_service: RabbitConfig,
    rabbit_queue: aio_pika.Queue,
    mocker: MockerFixture,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    app: FastAPI,
):
    _patch_settings_with_rabbit(app, rabbit_service)

    rabbit = RabbitMQ(app)
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

    await rabbit.post_log_message(log_msg)
    await rabbit.post_log_message(log_messages)

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
