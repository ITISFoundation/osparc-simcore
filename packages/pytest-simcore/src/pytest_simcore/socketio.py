# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections.abc import AsyncIterable, AsyncIterator, Callable
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from unittest.mock import AsyncMock

import pytest
import socketio
from aiohttp import web
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.users import UserID
from pytest_mock import MockerFixture
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager
from settings_library.rabbit import RabbitSettings
from socketio import AsyncAioPikaManager, AsyncServer
from yarl import URL


@pytest.fixture
async def socketio_server_factory() -> (
    Callable[[RabbitSettings], _AsyncGeneratorContextManager[AsyncServer]]
):
    @asynccontextmanager
    async def _(rabbit_settings: RabbitSettings) -> AsyncIterator[AsyncServer]:
        # Same configuration as simcore_service_webserver/socketio/server.py
        server_manager = AsyncAioPikaManager(url=rabbit_settings.dsn)

        server = AsyncServer(
            async_mode="aiohttp", engineio_logger=True, client_manager=server_manager
        )

        yield server

        await cleanup_socketio_async_pubsub_manager(server_manager)

    return _


@pytest.fixture
async def socketio_server() -> AsyncIterable[AsyncServer]:
    msg = "must be implemented in test"
    raise NotImplementedError(msg)


@pytest.fixture
async def web_server(
    socketio_server: AsyncServer, unused_tcp_port_factory: Callable[[], int]
) -> AsyncIterator[URL]:
    """
    this emulates the webserver setup: socketio server with
    an aiopika manager that attaches an aiohttp web app
    """
    aiohttp_app = web.Application()
    socketio_server.attach(aiohttp_app)

    server_port = unused_tcp_port_factory()

    runner = web.AppRunner(aiohttp_app)
    await runner.setup()

    site = web.TCPSite(runner, "localhost", server_port)
    await site.start()

    yield URL(f"http://localhost:{server_port}")

    await site.stop()
    await runner.cleanup()


@pytest.fixture
async def server_url(web_server: URL) -> str:
    return f"{web_server.with_path('/')}"


@pytest.fixture
def socketio_client_factory(
    server_url: str,
) -> Callable[[], _AsyncGeneratorContextManager[socketio.AsyncClient]]:
    @asynccontextmanager
    async def _() -> AsyncIterator[socketio.AsyncClient]:
        """This emulates a socketio client in the front-end"""
        client = socketio.AsyncClient(logger=True, engineio_logger=True)
        await client.connect(f"{server_url}", transports=["websocket"])

        yield client

        await client.disconnect()

    return _


@pytest.fixture
def room_name() -> SocketIORoomStr:
    msg = "must be implemented in test"
    raise NotImplementedError(msg)


@pytest.fixture
def socketio_server_events(
    socketio_server: AsyncServer,
    mocker: MockerFixture,
    user_id: UserID,
    room_name: SocketIORoomStr,
) -> dict[str, AsyncMock]:
    # handlers
    async def connect(sid: str, environ):
        print("connecting", sid)
        await socketio_server.enter_room(sid, room_name)

    async def on_check(sid, data):
        print("check", sid, data)

    async def disconnect(sid: str):
        print("disconnecting", sid)
        await socketio_server.leave_room(sid, room_name)

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
