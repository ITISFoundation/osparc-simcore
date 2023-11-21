from collections.abc import Callable

import pytest
import socketio
from aiohttp import web
from aiohttp.test_utils import TestServer
from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from settings_library.rabbit import RabbitSettings
from simcore_service_payments.services.socketio import (
    emit_to_frontend,
    get_rabbitmq_settings,
)
from socketio import AsyncAioPikaManager, AsyncServer

pytest_simcore_core_services_selection = [
    "rabbit",
]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
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
async def socketio_aiohttp_server(app: FastAPI, aiohttp_server: Callable) -> TestServer:
    """
    this emulates the webserver setup: socketio server with
    an aiopika manager that attaches an aiohttp web app
    """
    aiohttp_app = web.Application()

    # Emulates simcore_service_webserver/socketio/server.py
    settings: RabbitSettings = get_rabbitmq_settings(app)
    server_manager = AsyncAioPikaManager(url=settings.dsn)
    sio_server = AsyncServer(
        async_mode="aiohttp",
        engineio_logger=True,
        client_manager=server_manager,
    )

    @sio_server.event()
    async def connect(sid, environ):
        ...

    sio_server.attach(aiohttp_app)

    return await aiohttp_server(aiohttp_app)


async def test_emit_socketio_event_to_front_end(
    app: FastAPI, socketio_aiohttp_server: TestServer
):
    server_url = socketio_aiohttp_server.make_url("/")

    # create a client
    async with socketio.AsyncSimpleClient(logger=True, engineio_logger=True) as sio:

        # https://python-socketio.readthedocs.io/en/stable/client.html#connecting-to-a-server
        # connect to a server
        await sio.connect(server_url, transports=["websocket"])
        session_client_id = sio.sid

        # emit from external
        await emit_to_frontend(
            app, event_name="event", data={"foo": "bar"}, to=session_client_id
        )

        # client receives it
        event: list = await sio.receive(timeout=5)
        event_name, *event_kwargs = event

        assert event_name == "event"
