# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections.abc import AsyncIterable, Callable
from contextlib import AsyncExitStack, _AsyncGeneratorContextManager
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import socketio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_dynamic_sidecar.socketio import (
    SOCKET_IO_SERVICE_DISK_USAGE_EVENT,
)
from models_library.api_schemas_dynamic_sidecar.telemetry import (
    DiskUsage,
    ServiceDiskUsage,
)
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import ByteSize, NonNegativeInt, parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from servicelib.utils import logged_gather
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_sidecar.core.application import create_app
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.modules.system_monitor._disk_usage import (
    DiskUsageMonitor,
)
from simcore_service_dynamic_sidecar.modules.system_monitor._notifier import (
    publish_disk_usage,
)
from socketio import AsyncServer
from tenacity import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


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


def _get_on_service_disk_usage_event(
    socketio_client: socketio.AsyncClient,
) -> AsyncMock:
    # emulates front-end receiving message

    async def on_service_status(data):
        assert parse_obj_as(dict[Path, DiskUsage], data) is not None

    on_event_spy = AsyncMock(wraps=on_service_status)
    socketio_client.on(SOCKET_IO_SERVICE_DISK_USAGE_EVENT, on_event_spy)

    return on_event_spy


async def _assert_call_count(mock: AsyncMock, *, call_count: int) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1), stop=stop_after_attempt(5000), reraise=True
    ):
        with attempt:
            assert mock.call_count == call_count


def _get_mocked_disk_usage(byte_size_str: str) -> DiskUsage:
    return DiskUsage(
        total=ByteSize(0),
        used=ByteSize(0),
        free=ByteSize.validate(byte_size_str),
        used_percent=0,
    )


@pytest.mark.parametrize(
    "usage",
    [
        pytest.param({}, id="empty"),
        pytest.param({Path("/"): _get_mocked_disk_usage("1kb")}, id="one_entry"),
        pytest.param(
            {
                Path("/"): _get_mocked_disk_usage("1kb"),
                Path("/tmp"): _get_mocked_disk_usage("2kb"),  # noqa: S108
            },
            id="two_entries",
        ),
    ],
)
async def test_notifier_publish_message(
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

    number_of_clients: NonNegativeInt = 10
    async with AsyncExitStack() as socketio_frontend_clients:
        frontend_clients: list[socketio.AsyncClient] = await logged_gather(
            *[
                socketio_frontend_clients.enter_async_context(socketio_client_factory())
                for _ in range(number_of_clients)
            ]
        )
        await _assert_call_count(server_connect, call_count=number_of_clients)

        # client emits and check it was received
        await logged_gather(
            *[
                frontend_client.emit("check", data="an_event")
                for frontend_client in frontend_clients
            ]
        )
        await _assert_call_count(server_on_check, call_count=number_of_clients)

        # attach spy to client
        on_service_disk_usage_events: list[AsyncMock] = [
            _get_on_service_disk_usage_event(c) for c in frontend_clients
        ]

        # server publishes a message
        await publish_disk_usage(app, user_id=user_id, node_id=node_id, usage=usage)

        # check that all clients received it
        for on_service_disk_usage_event in on_service_disk_usage_events:
            await _assert_call_count(on_service_disk_usage_event, call_count=1)
            on_service_disk_usage_event.assert_awaited_once_with(
                jsonable_encoder(ServiceDiskUsage(node_id=node_id, usage=usage))
            )

    await _assert_call_count(server_disconnect, call_count=number_of_clients)
