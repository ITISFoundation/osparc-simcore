# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
import asyncio
import json
import uuid
from asyncio import AbstractEventLoop
from pathlib import Path
from pprint import pformat
from typing import Iterator, List

import aio_pika
import pytest
from _pytest.fixtures import FixtureRequest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.applications import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.settings.rabbit import RabbitConfig
from models_library.users import UserID
from pytest_mock.plugin import MockerFixture
from simcore_service_dynamic_sidecar.core.application import assemble_application
from simcore_service_dynamic_sidecar.core.rabbitmq import SLEEP_BETWEEN_SENDS, RabbitMQ
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


@pytest.fixture(scope="module")
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


@pytest.fixture
def mock_environment(
    event_loop: AbstractEventLoop,
    monkeypatch_module: MonkeyPatch,
    mock_dy_volumes: Path,
    compose_namespace: str,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: List[Path],
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    rabbit_service: RabbitConfig,
) -> None:
    monkeypatch_module.setenv("SC_BOOT_MODE", "production")
    monkeypatch_module.setenv("DYNAMIC_SIDECAR_COMPOSE_NAMESPACE", compose_namespace)
    monkeypatch_module.setenv("REGISTRY_AUTH", "false")
    monkeypatch_module.setenv("REGISTRY_USER", "test")
    monkeypatch_module.setenv("REGISTRY_PW", "test")
    monkeypatch_module.setenv("REGISTRY_SSL", "false")
    monkeypatch_module.setenv("DY_SIDECAR_USER_ID", f"{user_id}")
    monkeypatch_module.setenv("DY_SIDECAR_PROJECT_ID", f"{project_id}")
    monkeypatch_module.setenv("DY_SIDECAR_NODE_ID", f"{node_id}")
    monkeypatch_module.setenv("DY_SIDECAR_PATH_INPUTS", str(inputs_dir))
    monkeypatch_module.setenv("DY_SIDECAR_PATH_OUTPUTS", str(outputs_dir))
    monkeypatch_module.setenv(
        "DY_SIDECAR_STATE_PATHS", json.dumps([str(x) for x in state_paths_dirs])
    )
    monkeypatch_module.setenv("RABBIT_HOST", rabbit_service.host)
    monkeypatch_module.setenv("RABBIT_PORT", f"{rabbit_service.port}")
    monkeypatch_module.setenv("RABBIT_USER", rabbit_service.user)
    monkeypatch_module.setenv(
        "RABBIT_PASSWORD", rabbit_service.password.get_secret_value()
    )

    monkeypatch_module.setattr(mounted_fs, "DY_VOLUMES", mock_dy_volumes)


@pytest.fixture
def app(mock_environment: None) -> FastAPI:
    return assemble_application()


# UTILS


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
    rabbit = RabbitMQ(app)
    assert rabbit

    mock_close_connection_cb = mocker.patch(
        "simcore_service_dynamic_sidecar.core.rabbitmq._close_callback"
    )
    mock_close_channel_cb = mocker.patch(
        "simcore_service_dynamic_sidecar.core.rabbitmq._channel_close_callback"
    )

    incoming_data: List[LoggerRabbitMessage] = []

    async def rabbit_message_handler(message: aio_pika.IncomingMessage):
        incoming_data.append(LoggerRabbitMessage.parse_raw(message.body))

    await rabbit_queue.consume(rabbit_message_handler, exclusive=True, no_ack=True)

    await rabbit.connect()
    assert rabbit._connection.ready  # pylint: disable=protected-access

    log_msg: str = "I am logging"
    log_messages: List[str] = ["I", "am a logger", "man..."]
    log_more_messages: List[str] = [f"msg{1}" for i in range(10)]

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
