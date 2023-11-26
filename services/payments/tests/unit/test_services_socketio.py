# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import asyncio
from collections.abc import Callable
from typing import Any, Awaitable
from unittest.mock import AsyncMock

import pytest
import socketio
from aiohttp import web
from aiohttp.test_utils import TestServer
from fastapi import FastAPI
from models_library.api_schemas_payments.socketio import (
    SOCKET_IO_PAYMENT_COMPLETED_EVENT,
)
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from settings_library.rabbit import RabbitSettings
from simcore_service_payments.services.rabbitmq import get_rabbitmq_settings
from simcore_service_payments.services.socketio import notify_payment_completed
from socketio import AsyncAioPikaManager, AsyncServer

pytest_simcore_core_services_selection = [
    "rabbit",
]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    with_disabled_postgres: None,
    rabbit_env_vars_dict: EnvVarsDict,  # rabbitMQ settings from 'rabbit' service
):
    # set environs
    monkeypatch.delenv("PAYMENTS_RABBITMQ", raising=False)

    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **rabbit_env_vars_dict,
        },
    )


async def test_socketio_setup():
    # is this closing properly?
    ...


@pytest.fixture
async def socketio_server(app: FastAPI) -> AsyncServer:
    """
    this emulates the webserver setup: socketio server with
    an aiopika manager that attaches an aiohttp web app
    """
    # Same configuration as simcore_service_webserver/socketio/server.py
    settings: RabbitSettings = get_rabbitmq_settings(app)
    server_manager = AsyncAioPikaManager(url=settings.dsn)

    sio_server = AsyncServer(
        async_mode="aiohttp",
        engineio_logger=True,
        client_manager=server_manager,
    )
    return sio_server


def socketio_events(
    sio_server: AsyncServer, mocker: MockerFixture
) -> dict[str, AsyncMock]:

    # handlers & spies
    async def connect(sid: str, environ):
        print("connecting", sid)

    spy_connect = mocker.AsyncMock(wraps=connect)
    sio_server.event()(spy_connect)

    async def on_payment(sid, data):
        print(sid, Any)

    spy_on_payment = mocker.AsyncMock(wraps=on_payment)
    sio_server.on(SOCKET_IO_PAYMENT_COMPLETED_EVENT, spy_on_payment)

    async def disconnect(sid: str):
        print("disconnecting", sid)

    spy_disconnect = mocker.AsyncMock(wraps=disconnect)
    sio_server.event()(spy_disconnect)

    return {
        connect.__name__: spy_on_payment,
        on_payment.__name__: spy_on_payment,
        disconnect.__name__: spy_disconnect,
    }


@pytest.fixture()
async def web_server(socketio_server: AsyncServer, aiohttp_server: Callable):
    aiohttp_app = web.Application()
    socketio_server.attach(aiohttp_app)

    # starts server
    return await aiohttp_server(aiohttp_app)


@pytest.fixture
async def server_url(web_server: TestServer) -> str:
    return f'{web_server.make_url("/")}'


@pytest.fixture
async def create_sio_client(server_url: str):
    _clients = []

    async def _():
        cli = socketio.AsyncClient(
            logger=True,
            engineio_logger=True,
        )

        # https://python-socketio.readthedocs.io/en/stable/client.html#connecting-to-a-server
        # Allows WebSocket transport and disconnect HTTP long-polling
        await cli.connect(f"{server_url}", transports=["websocket"])

        _clients.append(cli)

        return cli

    yield _

    for client in _clients:
        await client.disconnect()


async def test_emit_message_as_external_process_to_frontend_client(
    app: FastAPI, create_sio_client: Callable[..., Awaitable[socketio.AsyncClient]]
):
    """
    front-end  -> socketio client (many different clients)
    webserver  -> socketio server (one/more replicas)
    payments   -> Sends messages to clients from external processes (one/more replicas)
    """

    # emulates front-end receiving message
    client_1: socketio.AsyncClient = await create_sio_client()

    @client_1.on(SOCKET_IO_PAYMENT_COMPLETED_EVENT)
    async def on_event(data):
        print("client1", data)

    on_event_spy = AsyncMock(wraps=on_event)

    await client_1.emit(SOCKET_IO_PAYMENT_COMPLETED_EVENT, data="hoi1")

    # TODO: better to do this from a different process??
    # emit from external process

    await notify_payment_completed()

    await emit_to_frontend(
        app,
        event_name=SOCKET_IO_PAYMENT_COMPLETED_EVENT,
        data={"foo": "bar"},
        # to=client_1.sid,
    )

    await client_1.emit(SOCKET_IO_PAYMENT_COMPLETED_EVENT, data="hoi2")

    await client_1.sleep(1)
    await asyncio.sleep(1)

    on_event_spy.assert_called()
