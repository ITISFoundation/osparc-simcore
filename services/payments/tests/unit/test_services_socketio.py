# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import asyncio
from collections.abc import Callable
from typing import Any, AsyncIterable
from unittest.mock import AsyncMock

import pytest
import socketio
from aiohttp import web
from aiohttp.test_utils import TestServer
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_payments.socketio import (
    SOCKET_IO_PAYMENT_COMPLETED_EVENT,
)
from models_library.users import GroupID
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.rawdata_fakers import random_payment_transaction
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager
from settings_library.rabbit import RabbitSettings
from simcore_service_payments.models.db import PaymentsTransactionsDB
from simcore_service_payments.services.rabbitmq import get_rabbitmq_settings
from simcore_service_payments.services.socketio import notify_payment_completed
from socketio import AsyncAioPikaManager, AsyncServer
from tenacity import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

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


@pytest.fixture
def user_primary_group_id(faker: Faker) -> GroupID:
    return parse_obj_as(GroupID, faker.pyint())


@pytest.fixture
async def socketio_server(app: FastAPI) -> AsyncIterable[AsyncServer]:
    # Same configuration as simcore_service_webserver/socketio/server.py
    settings: RabbitSettings = get_rabbitmq_settings(app)
    server_manager = AsyncAioPikaManager(url=settings.dsn)

    server = AsyncServer(
        async_mode="aiohttp",
        engineio_logger=True,
        client_manager=server_manager,
    )

    yield server

    await cleanup_socketio_async_pubsub_manager(server_manager)
    await server.shutdown()


@pytest.fixture
def socketio_server_events(
    socketio_server: AsyncServer,
    mocker: MockerFixture,
    user_primary_group_id: GroupID,
) -> dict[str, AsyncMock]:

    user_room_name = f"{user_primary_group_id}"

    # handlers
    async def connect(sid: str, environ):
        print("connecting", sid)
        await socketio_server.enter_room(sid, user_room_name)

    async def on_check(sid, data):
        print("check", sid, Any)

    async def on_payment(sid, data):
        print("payment", sid, Any)

    async def disconnect(sid: str):
        print("disconnecting", sid)
        await socketio_server.leave_room(sid, user_room_name)

    # spies
    spy_connect = mocker.AsyncMock(wraps=connect)
    socketio_server.on("connect", spy_connect)

    spy_on_payment = mocker.AsyncMock(wraps=on_payment)
    socketio_server.on(SOCKET_IO_PAYMENT_COMPLETED_EVENT, spy_on_payment)

    spy_on_check = mocker.AsyncMock(wraps=on_check)
    socketio_server.on("check", spy_on_check)

    spy_disconnect = mocker.AsyncMock(wraps=disconnect)
    socketio_server.on("disconnect", spy_disconnect)

    return {
        connect.__name__: spy_on_payment,
        disconnect.__name__: spy_disconnect,
        on_check.__name__: spy_on_check,
        on_payment.__name__: spy_on_payment,
    }


@pytest.fixture
async def web_server(socketio_server: AsyncServer, aiohttp_server: Callable):
    """
    this emulates the webserver setup: socketio server with
    an aiopika manager that attaches an aiohttp web app
    """
    aiohttp_app = web.Application()
    socketio_server.attach(aiohttp_app)

    # starts server
    return await aiohttp_server(aiohttp_app)


@pytest.fixture
async def server_url(web_server: TestServer) -> str:
    return f'{web_server.make_url("/")}'


@pytest.fixture
async def socketio_client(server_url: str) -> AsyncIterable[socketio.AsyncClient]:
    client = socketio.AsyncClient(logger=True, engineio_logger=True)
    await client.connect(f"{server_url}", transports=["websocket"])

    yield client

    await client.disconnect()


@pytest.fixture
async def socketio_client_events(
    socketio_client: socketio.AsyncClient,
) -> dict[str, AsyncMock]:
    # emulates front-end receiving message
    async def on_event(data):
        print("client1", data)

    on_event_spy = AsyncMock(wraps=on_event)
    socketio_client.on(SOCKET_IO_PAYMENT_COMPLETED_EVENT, on_event_spy)

    return {on_event.__name__: on_event_spy}


@pytest.fixture
async def notify_payment(app: FastAPI, user_primary_group_id: GroupID) -> Callable:
    async def _():
        payment = PaymentsTransactionsDB(**random_payment_transaction()).to_api_model()
        await notify_payment_completed(
            app, user_primary_group_id=user_primary_group_id, payment=payment
        )

    return _


async def test_emit_message_as_external_process_to_frontend_client(
    app: FastAPI,
    web_server: socketio.AsyncServer,
    socketio_server_events: dict[str, AsyncMock],
    socketio_client: socketio.AsyncClient,
    socketio_client_events: dict[str, AsyncMock],
    notify_payment: Callable,
):
    """
    front-end  -> socketio client (many different clients)
    webserver  -> socketio server (one/more replicas)
    payments   -> Sends messages to clients from external processes (one/more replicas)
    """

    # web server events
    connect_spy = socketio_server_events["connect"]
    on_check_spy = socketio_server_events["on_check"]

    assert connect_spy.called
    assert not on_check_spy.called

    await socketio_client.emit("check", data="hoi")
    assert on_check_spy.called

    # client events
    await notify_payment()

    on_event_spy = socketio_client_events["on_event"]

    async for attempt in AsyncRetrying(
        wait=wait_fixed(2), stop=stop_after_attempt(5), reraise=True
    ):
        with attempt:
            await asyncio.sleep(0.1)
            on_event_spy.assert_called()
