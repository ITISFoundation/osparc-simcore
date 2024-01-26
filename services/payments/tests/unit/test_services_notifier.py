# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import asyncio
import threading
from collections.abc import AsyncIterable, AsyncIterator, Callable
from unittest.mock import AsyncMock

import arrow
import pytest
import socketio
from aiohttp import web
from aiohttp.test_utils import TestServer
from fastapi import FastAPI
from models_library.api_schemas_payments.socketio import (
    SOCKET_IO_PAYMENT_COMPLETED_EVENT,
)
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.api_schemas_webserver.wallets import PaymentTransaction
from models_library.users import GroupID, UserID
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.rawdata_fakers import random_payment_transaction
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager
from settings_library.rabbit import RabbitSettings
from simcore_service_payments.models.db import PaymentsTransactionsDB
from simcore_service_payments.models.db_to_api import to_payments_api_model
from simcore_service_payments.services.notifier import Notifier
from simcore_service_payments.services.rabbitmq import get_rabbitmq_settings
from socketio import AsyncAioPikaManager, AsyncServer
from tenacity import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from yarl import URL

pytest_simcore_core_services_selection = [
    "rabbit",
]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def mock_db_payments_users_repo(mocker: MockerFixture, user_primary_group_id: GroupID):
    mocker.patch(
        "simcore_service_payments.db.payment_users_repo.PaymentsUsersRepo.get_primary_group_id",
        return_value=user_primary_group_id,
    )


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,  # rabbitMQ settings from 'rabbit' service
    # db layer is mocked
    with_disabled_postgres: None,
    mock_db_payments_users_repo: None,
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


@pytest.fixture
def socketio_server_events(
    socketio_server: AsyncServer,
    mocker: MockerFixture,
    user_primary_group_id: GroupID,
) -> dict[str, AsyncMock]:
    room_name = SocketIORoomStr.from_group_id(user_primary_group_id)

    # handlers
    async def connect(sid: str, environ):
        print("connecting", sid)
        await socketio_server.enter_room(sid, room_name)

    async def on_check(sid, data):
        print("check", sid, data)

    async def on_payment(sid, data):
        print("payment", sid, parse_obj_as(PaymentTransaction, data))

    async def disconnect(sid: str):
        print("disconnecting", sid)
        await socketio_server.leave_room(sid, room_name)

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
        connect.__name__: spy_connect,
        disconnect.__name__: spy_disconnect,
        on_check.__name__: spy_on_check,
        on_payment.__name__: spy_on_payment,
    }


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

    server = TestServer(aiohttp_app, port=unused_tcp_port_factory())
    t = asyncio.create_task(_lifespan(server, setup, teardown), name="server-lifespan")

    await setup.wait()

    yield URL(server.make_url("/"))

    assert t
    teardown.set()


@pytest.fixture
async def server_url(web_server: URL) -> str:
    return f'{web_server.with_path("/")}'


@pytest.fixture
async def socketio_client(server_url: str) -> AsyncIterable[socketio.AsyncClient]:
    """This emulates a socketio client in the front-end"""
    client = socketio.AsyncClient(logger=True, engineio_logger=True)
    await client.connect(f"{server_url}", transports=["websocket"])

    yield client

    await client.disconnect()


@pytest.fixture
async def socketio_client_events(
    socketio_client: socketio.AsyncClient,
) -> dict[str, AsyncMock]:
    # emulates front-end receiving message

    async def on_payment(data):
        assert parse_obj_as(PaymentTransaction, data) is not None

    on_event_spy = AsyncMock(wraps=on_payment)
    socketio_client.on(SOCKET_IO_PAYMENT_COMPLETED_EVENT, on_event_spy)

    return {on_payment.__name__: on_event_spy}


@pytest.fixture
async def notify_payment(app: FastAPI, user_id: UserID) -> Callable:
    async def _():
        transaction = PaymentsTransactionsDB(
            **random_payment_transaction(
                user_id=user_id, completed_at=arrow.utcnow().datetime
            )
        )
        notifier: Notifier = Notifier.get_from_app_state(app)
        await notifier.notify_payment_completed(
            user_id=transaction.user_id, payment=to_payments_api_model(transaction)
        )

    return _


async def test_emit_message_as_external_process_to_frontend_client(
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
    # Used iusntead of a fix asyncio.sleep
    context_switch_retry_kwargs = {
        "wait": wait_fixed(0.1),
        "stop": stop_after_attempt(5),
        "reraise": True,
    }

    # web server spy events
    server_connect = socketio_server_events["connect"]
    server_disconnect = socketio_server_events["disconnect"]
    server_on_check = socketio_server_events["on_check"]
    server_on_payment = socketio_server_events["on_payment"]

    # client spy events
    client_on_payment = socketio_client_events["on_payment"]

    # checks
    assert server_connect.called
    assert not server_disconnect.called

    # client emits
    await socketio_client.emit("check", data="hoi")

    async for attempt in AsyncRetrying(**context_switch_retry_kwargs):
        with attempt:
            assert server_on_check.called

    # payment server emits
    def _(lp):
        asyncio.run_coroutine_threadsafe(notify_payment(), lp)

    threading.Thread(
        target=_,
        args=(asyncio.get_event_loop(),),
        daemon=False,
    ).start()

    async for attempt in AsyncRetrying(**context_switch_retry_kwargs):
        with attempt:
            assert client_on_payment.called
            assert not server_on_payment.called
