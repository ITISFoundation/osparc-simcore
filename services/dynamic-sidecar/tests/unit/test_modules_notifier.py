# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections.abc import AsyncIterable, Callable
from contextlib import AsyncExitStack, _AsyncGeneratorContextManager
from pathlib import Path
from typing import Final
from unittest.mock import AsyncMock

import pytest
import socketio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_dynamic_sidecar.ports import (
    InputPortSatus,
    InputStatus,
    OutputPortStatus,
    OutputStatus,
)
from models_library.api_schemas_dynamic_sidecar.socketio import (
    SOCKET_IO_SERVICE_DISK_USAGE_EVENT,
    SOCKET_IO_STATE_INPUT_PORTS_EVENT,
    SOCKET_IO_STATE_OUTPUT_PORTS_EVENT,
)
from models_library.api_schemas_dynamic_sidecar.telemetry import (
    DiskUsage,
    MountPathCategory,
    ServiceDiskUsage,
)
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServicePortKey
from models_library.users import UserID
from pydantic import ByteSize, NonNegativeInt, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.utils import logged_gather
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_sidecar.core.application import create_app
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.modules.notifications import (
    PortNotifier,
    publish_disk_usage,
)
from simcore_service_dynamic_sidecar.modules.system_monitor._disk_usage import (
    DiskUsageMonitor,
)
from socketio import AsyncServer
from tenacity import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]

_NUMBER_OF_CLIENTS: Final[NonNegativeInt] = 10


@pytest.fixture
def mock_environment(
    monkeypatch: pytest.MonkeyPatch,
    rabbit_service: RabbitSettings,
    mock_environment: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            "DY_SIDECAR_SYSTEM_MONITOR_TELEMETRY_ENABLE": "true",
            "RABBIT_HOST": rabbit_service.RABBIT_HOST,
            "RABBIT_PASSWORD": rabbit_service.RABBIT_PASSWORD.get_secret_value(),
            "RABBIT_PORT": f"{rabbit_service.RABBIT_PORT}",
            "RABBIT_SECURE": f"{rabbit_service.RABBIT_SECURE}",
            "RABBIT_USER": rabbit_service.RABBIT_USER,
        },
    )


@pytest.fixture
async def app(
    mock_environment: EnvVarsDict,
    mock_registry_service: AsyncMock,
    mock_storage_check: None,
    mock_postgres_check: None,
    mocker: MockerFixture,
) -> AsyncIterable[FastAPI]:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.system_monitor._disk_usage._get_monitored_paths",
        return_value=[],
    )

    app: FastAPI = create_app()
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def disk_usage_monitor(app: FastAPI) -> DiskUsageMonitor:
    return app.state.disk_usage_monitor


@pytest.fixture
async def socketio_server(
    app: FastAPI,
    socketio_server_factory: Callable[
        [RabbitSettings], _AsyncGeneratorContextManager[AsyncServer]
    ],
) -> AsyncIterable[AsyncServer]:
    # Same configuration as simcore_service_webserver/socketio/server.py
    settings: ApplicationSettings = app.state.settings
    assert settings.RABBIT_SETTINGS

    async with socketio_server_factory(settings.RABBIT_SETTINGS) as server:
        yield server


@pytest.fixture
def room_name(user_id: UserID) -> SocketIORoomStr:
    return SocketIORoomStr.from_user_id(user_id)


async def _assert_call_count(mock: AsyncMock, *, call_count: int) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1), stop=stop_after_delay(5), reraise=True
    ):
        with attempt:
            assert mock.call_count == call_count


def _get_mocked_disk_usage(byte_size_str: str) -> DiskUsage:
    return DiskUsage(
        total=TypeAdapter(ByteSize).validate_python(byte_size_str),
        used=ByteSize(0),
        free=TypeAdapter(ByteSize).validate_python(byte_size_str),
        used_percent=0,
    )


def _get_on_service_disk_usage_spy(
    socketio_client: socketio.AsyncClient,
) -> AsyncMock:
    # emulates front-end receiving message

    async def on_service_status(data):
        assert TypeAdapter(ServiceDiskUsage).validate_python(data) is not None

    on_event_spy = AsyncMock(wraps=on_service_status)
    socketio_client.on(SOCKET_IO_SERVICE_DISK_USAGE_EVENT, on_event_spy)

    return on_event_spy


@pytest.mark.parametrize(
    "usage",
    [
        pytest.param({}, id="empty"),
        pytest.param(
            {MountPathCategory.HOST: _get_mocked_disk_usage("1kb")}, id="one_entry"
        ),
        pytest.param(
            {
                MountPathCategory.HOST: _get_mocked_disk_usage("1kb"),
                MountPathCategory.STATES_VOLUMES: _get_mocked_disk_usage("2kb"),
            },
            id="two_entries",
        ),
    ],
)
async def test_notifier_publish_disk_usage(
    disk_usage_monitor: DiskUsageMonitor,
    socketio_server_events: dict[str, AsyncMock],
    app: FastAPI,
    user_id: UserID,
    usage: dict[Path, DiskUsage],
    node_id: NodeID,
    socketio_client_factory: Callable[
        [], _AsyncGeneratorContextManager[socketio.AsyncClient]
    ],
):
    # web server spy events
    server_connect = socketio_server_events["connect"]
    server_disconnect = socketio_server_events["disconnect"]
    server_on_check = socketio_server_events["on_check"]

    async with AsyncExitStack() as socketio_frontend_clients:
        frontend_clients: list[socketio.AsyncClient] = await logged_gather(
            *[
                socketio_frontend_clients.enter_async_context(socketio_client_factory())
                for _ in range(_NUMBER_OF_CLIENTS)
            ]
        )
        await _assert_call_count(server_connect, call_count=_NUMBER_OF_CLIENTS)

        # client emits and check it was received
        await logged_gather(
            *[
                frontend_client.emit("check", data="an_event")
                for frontend_client in frontend_clients
            ]
        )
        await _assert_call_count(server_on_check, call_count=_NUMBER_OF_CLIENTS)

        # attach spy to client
        on_service_disk_usage_events: list[AsyncMock] = [
            _get_on_service_disk_usage_spy(c) for c in frontend_clients
        ]

        # server publishes a message
        await publish_disk_usage(app, user_id=user_id, node_id=node_id, usage=usage)

        # check that all clients received it
        for on_service_disk_usage_event in on_service_disk_usage_events:
            await _assert_call_count(on_service_disk_usage_event, call_count=1)
            on_service_disk_usage_event.assert_awaited_once_with(
                jsonable_encoder(ServiceDiskUsage(node_id=node_id, usage=usage))
            )

    await _assert_call_count(server_disconnect, call_count=_NUMBER_OF_CLIENTS)


@pytest.fixture
def port_key() -> ServicePortKey:
    return TypeAdapter(ServicePortKey).validate_python("test_port")


def _get_on_input_port_spy(
    socketio_client: socketio.AsyncClient,
) -> AsyncMock:
    # emulates front-end receiving message

    async def on_service_status(data):
        assert TypeAdapter(ServiceDiskUsage).validate_python(data) is not None

    on_event_spy = AsyncMock(wraps=on_service_status)
    socketio_client.on(SOCKET_IO_STATE_INPUT_PORTS_EVENT, on_event_spy)

    return on_event_spy


@pytest.mark.parametrize("input_status", InputStatus)
async def test_notifier_send_input_port_status(
    socketio_server_events: dict[str, AsyncMock],
    app: FastAPI,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    port_key: ServicePortKey,
    socketio_client_factory: Callable[
        [], _AsyncGeneratorContextManager[socketio.AsyncClient]
    ],
    input_status: InputStatus,
):
    # web server spy events
    server_connect = socketio_server_events["connect"]
    server_disconnect = socketio_server_events["disconnect"]
    server_on_check = socketio_server_events["on_check"]

    async with AsyncExitStack() as socketio_frontend_clients:
        frontend_clients: list[socketio.AsyncClient] = await logged_gather(
            *[
                socketio_frontend_clients.enter_async_context(socketio_client_factory())
                for _ in range(_NUMBER_OF_CLIENTS)
            ]
        )
        await _assert_call_count(server_connect, call_count=_NUMBER_OF_CLIENTS)

        # client emits and check it was received
        await logged_gather(
            *[
                frontend_client.emit("check", data="an_event")
                for frontend_client in frontend_clients
            ]
        )
        await _assert_call_count(server_on_check, call_count=_NUMBER_OF_CLIENTS)

        # attach spy to client
        on_input_port_events: list[AsyncMock] = [
            _get_on_input_port_spy(c) for c in frontend_clients
        ]

        port_notifier = PortNotifier(app, user_id, project_id, node_id)

        # server publishes a message
        match input_status:
            case InputStatus.DOWNLOAD_STARTED:
                await port_notifier.send_input_port_download_started(port_key)
            case InputStatus.DOWNLOAD_WAS_ABORTED:
                await port_notifier.send_input_port_download_was_aborted(port_key)
            case InputStatus.DOWNLOAD_FINISHED_SUCCESSFULLY:
                await port_notifier.send_input_port_download_finished_succesfully(
                    port_key
                )
            case InputStatus.DOWNLOAD_FINISHED_WITH_ERROR:
                await port_notifier.send_input_port_download_finished_with_error(
                    port_key
                )

        # check that all clients received it
        for on_input_port_event in on_input_port_events:
            await _assert_call_count(on_input_port_event, call_count=1)
            on_input_port_event.assert_awaited_once_with(
                jsonable_encoder(
                    InputPortSatus(
                        project_id=project_id,
                        node_id=node_id,
                        port_key=port_key,
                        status=input_status,
                    )
                )
            )

    await _assert_call_count(server_disconnect, call_count=_NUMBER_OF_CLIENTS)


def _get_on_output_port_spy(
    socketio_client: socketio.AsyncClient,
) -> AsyncMock:
    # emulates front-end receiving message

    async def on_service_status(data):
        assert TypeAdapter(ServiceDiskUsage).validate_python(data) is not None

    on_event_spy = AsyncMock(wraps=on_service_status)
    socketio_client.on(SOCKET_IO_STATE_OUTPUT_PORTS_EVENT, on_event_spy)

    return on_event_spy


@pytest.mark.parametrize("output_status", OutputStatus)
async def test_notifier_send_output_port_status(
    socketio_server_events: dict[str, AsyncMock],
    app: FastAPI,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    port_key: ServicePortKey,
    socketio_client_factory: Callable[
        [], _AsyncGeneratorContextManager[socketio.AsyncClient]
    ],
    output_status: OutputStatus,
):
    # web server spy events
    server_connect = socketio_server_events["connect"]
    server_disconnect = socketio_server_events["disconnect"]
    server_on_check = socketio_server_events["on_check"]

    async with AsyncExitStack() as socketio_frontend_clients:
        frontend_clients: list[socketio.AsyncClient] = await logged_gather(
            *[
                socketio_frontend_clients.enter_async_context(socketio_client_factory())
                for _ in range(_NUMBER_OF_CLIENTS)
            ]
        )
        await _assert_call_count(server_connect, call_count=_NUMBER_OF_CLIENTS)

        # client emits and check it was received
        await logged_gather(
            *[
                frontend_client.emit("check", data="an_event")
                for frontend_client in frontend_clients
            ]
        )
        await _assert_call_count(server_on_check, call_count=_NUMBER_OF_CLIENTS)

        # attach spy to client
        on_output_port_events: list[AsyncMock] = [
            _get_on_output_port_spy(c) for c in frontend_clients
        ]

        port_notifier = PortNotifier(app, user_id, project_id, node_id)

        # server publishes a message
        match output_status:
            case OutputStatus.UPLOAD_STARTED:
                await port_notifier.send_output_port_upload_sarted(port_key)
            case OutputStatus.UPLOAD_WAS_ABORTED:
                await port_notifier.send_output_port_upload_was_aborted(port_key)
            case OutputStatus.UPLOAD_FINISHED_SUCCESSFULLY:
                await port_notifier.send_output_port_upload_finished_successfully(
                    port_key
                )
            case OutputStatus.UPLOAD_FINISHED_WITH_ERROR:
                await port_notifier.send_output_port_upload_finished_with_error(
                    port_key
                )

        # check that all clients received it
        for on_output_port_event in on_output_port_events:
            await _assert_call_count(on_output_port_event, call_count=1)
            on_output_port_event.assert_awaited_once_with(
                jsonable_encoder(
                    OutputPortStatus(
                        project_id=project_id,
                        node_id=node_id,
                        port_key=port_key,
                        status=output_status,
                    )
                )
            )

    await _assert_call_count(server_disconnect, call_count=_NUMBER_OF_CLIENTS)
