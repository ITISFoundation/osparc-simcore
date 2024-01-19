# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
from collections.abc import AsyncIterable, AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import socketio
from aiohttp import web
from aiohttp.test_utils import TestServer
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
from models_library.projects_nodes_io import NodeID
from models_library.users import GroupID
from pydantic import ByteSize, NonNegativeInt, parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager
from servicelib.utils import logged_gather
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.modules.system_monitor._disk_usage import (
    DiskUsageMonitor,
)
from simcore_service_dynamic_sidecar.modules.system_monitor._notifier import (
    publish_disk_usage,
)
from socketio import AsyncAioPikaManager, AsyncServer
from tenacity import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from yarl import URL

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def mock_environment(
    monkeypatch: pytest.MonkeyPatch,
    mock_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
) -> EnvVarsDict:
    setenvs_from_dict(
        monkeypatch, {"DY_SIDECAR_SYSTEM_MONITOR_TELEMETRY_ENABLE": "true"}
    )
    return mock_environment


@pytest.fixture
async def app(mocker: MockerFixture, app: FastAPI) -> AsyncIterable[FastAPI]:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.system_monitor._disk_usage._get_monitored_paths",
        return_value=[],
    )
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def disk_usage_monitor(app: FastAPI) -> DiskUsageMonitor:
    return app.state.disk_usage_monitor


@pytest.fixture
async def socketio_server(app: FastAPI) -> AsyncIterable[AsyncServer]:
    # Same configuration as simcore_service_webserver/socketio/server.py
    settings: ApplicationSettings = app.state.settings
    assert settings.RABBIT_SETTINGS
    server_manager = AsyncAioPikaManager(url=settings.RABBIT_SETTINGS.dsn)

    server = AsyncServer(
        async_mode="aiohttp", engineio_logger=True, client_manager=server_manager
    )

    yield server

    await cleanup_socketio_async_pubsub_manager(server_manager)


@pytest.fixture
async def web_server(
    socketio_server: AsyncServer, aiohttp_unused_port: Callable
) -> AsyncIterator[URL]:
    """
    this emulates the webserver setup: socketio server with
    an aiopika manager that attaches an aiohttp web app
    """
    aiohttp_app = web.Application()
    socketio_server.attach(aiohttp_app)

    async def _lifespan(
        server: TestServer, started: asyncio.Event, teardown: asyncio.Event
    ):
        # NOTE: this is necessary to avoid blocking comms between client and this server
        await server.start_server()
        started.set()  # notifies started
        await teardown.wait()  # keeps test0server until needs to close
        await server.close()

    setup = asyncio.Event()
    teardown = asyncio.Event()

    server = TestServer(aiohttp_app, port=aiohttp_unused_port())
    t = asyncio.create_task(_lifespan(server, setup, teardown), name="server-lifespan")

    await setup.wait()

    yield URL(server.make_url("/"))

    assert t
    teardown.set()


@pytest.fixture
async def server_url(web_server: URL) -> str:
    return f'{web_server.with_path("/")}'

    return 4


@pytest.fixture
def socketio_server_events(
    socketio_server: AsyncServer,
    mocker: MockerFixture,
    primary_group_id: GroupID,
) -> dict[str, AsyncMock]:
    user_room_name = f"{primary_group_id}"

    # handlers
    async def connect(sid: str, environ):
        print("connecting", sid)
        await socketio_server.enter_room(sid, user_room_name)

    async def on_check(sid, data):
        print("check", sid, data)

    async def disconnect(sid: str):
        print("disconnecting", sid)
        await socketio_server.leave_room(sid, user_room_name)

    # spies
    spy_connect = mocker.AsyncMock(wraps=connect)
    socketio_server.on("connect", spy_connect)

    spy_on_check = mocker.AsyncMock(wraps=on_check)
    socketio_server.on("check", spy_on_check)

    spy_disconnect = mocker.AsyncMock(wraps=disconnect)
    socketio_server.on("disconnect", spy_disconnect)

    return {
        connect.__name__: spy_connect,
        disconnect.__name__: spy_disconnect,
        on_check.__name__: spy_on_check,
    }


@asynccontextmanager
async def get_socketio_client(server_url: str) -> AsyncIterator[socketio.AsyncClient]:
    """This emulates a socketio client in the front-end"""
    client = socketio.AsyncClient(logger=True, engineio_logger=True)
    await client.connect(f"{server_url}", transports=["websocket"])

    yield client

    await client.disconnect()


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
    return DiskUsage(total=0, used=0, free=ByteSize.validate(byte_size_str), percent=0)


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
    server_url: str,
    app: FastAPI,
    primary_group_id: GroupID,
    usage: dict[Path, DiskUsage],
    node_id: NodeID,
):
    # web server spy events
    server_connect = socketio_server_events["connect"]
    server_disconnect = socketio_server_events["disconnect"]
    server_on_check = socketio_server_events["on_check"]

    number_of_clients: NonNegativeInt = 10
    async with AsyncExitStack() as socketio_frontend_clients:
        frontend_clients: list[socketio.AsyncClient] = await logged_gather(
            *[
                socketio_frontend_clients.enter_async_context(
                    get_socketio_client(server_url)
                )
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
        await publish_disk_usage(
            app, primary_group_id=primary_group_id, node_id=node_id, usage=usage
        )

        # check that all clients received it
        for on_service_disk_usage_event in on_service_disk_usage_events:
            await _assert_call_count(on_service_disk_usage_event, call_count=1)
            on_service_disk_usage_event.assert_awaited_once_with(
                jsonable_encoder(ServiceDiskUsage(node_id=node_id, usage=usage))
            )

    await _assert_call_count(server_disconnect, call_count=number_of_clients)
