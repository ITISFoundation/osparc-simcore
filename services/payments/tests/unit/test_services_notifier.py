# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterable, Callable
from contextlib import _AsyncGeneratorContextManager
from typing import Awaitable
from unittest.mock import AsyncMock

import arrow
import pytest
import socketio
from fastapi import FastAPI
from models_library.api_schemas_payments.socketio import (
    SOCKET_IO_PAYMENT_COMPLETED_EVENT,
)
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.api_schemas_webserver.wallets import PaymentTransaction
from models_library.users import GroupID, UserID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.faker_factories import random_payment_transaction
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from simcore_service_payments.models.db import PaymentsTransactionsDB
from simcore_service_payments.models.db_to_api import to_payments_api_model
from simcore_service_payments.services.notifier import NotifierService
from simcore_service_payments.services.rabbitmq import get_rabbitmq_settings
from socketio import AsyncServer
from tenacity import AsyncRetrying, stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


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
    monkeypatch.delenv("PAYMENTS_EMAIL", raising=False)

    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **rabbit_env_vars_dict,
        },
    )


@pytest.fixture
async def socketio_server(
    app: FastAPI,
    socketio_server_factory: Callable[
        [RabbitSettings], _AsyncGeneratorContextManager[AsyncServer]
    ],
) -> AsyncIterable[AsyncServer]:
    async with socketio_server_factory(get_rabbitmq_settings(app)) as server:
        yield server


@pytest.fixture
def room_name(user_primary_group_id: GroupID) -> SocketIORoomStr:
    return SocketIORoomStr.from_group_id(user_primary_group_id)


@pytest.fixture
async def socketio_client(
    socketio_client_factory: Callable[
        [], _AsyncGeneratorContextManager[socketio.AsyncClient]
    ],
) -> AsyncIterable[socketio.AsyncClient]:
    async with socketio_client_factory() as client:
        yield client


@pytest.fixture
async def socketio_client_events(
    socketio_client: socketio.AsyncClient,
) -> dict[str, AsyncMock]:
    # emulates front-end receiving message

    async def on_payment(data):
        assert TypeAdapter(PaymentTransaction).validate_python(data) is not None

    on_event_spy = AsyncMock(wraps=on_payment)
    socketio_client.on(SOCKET_IO_PAYMENT_COMPLETED_EVENT, on_event_spy)

    return {on_payment.__name__: on_event_spy}


@pytest.fixture
async def notify_payment(
    app: FastAPI, user_id: UserID
) -> Callable[[], Awaitable[None]]:
    async def _() -> None:
        transaction = PaymentsTransactionsDB(
            **random_payment_transaction(
                user_id=user_id, completed_at=arrow.utcnow().datetime
            )
        )
        notifier: NotifierService = NotifierService.get_from_app_state(app)
        await notifier.notify_payment_completed(
            user_id=transaction.user_id, payment=to_payments_api_model(transaction)
        )

    return _


async def _assert_called_once(mock: AsyncMock) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1), stop=stop_after_delay(5), reraise=True
    ):
        with attempt:
            assert mock.call_count == 1


async def test_emit_message_as_external_process_to_frontend_client(
    socketio_server_events: dict[str, AsyncMock],
    socketio_client: socketio.AsyncClient,
    socketio_client_events: dict[str, AsyncMock],
    notify_payment: Callable[[], Awaitable[None]],
    socketio_client_factory: Callable[
        [], _AsyncGeneratorContextManager[socketio.AsyncClient]
    ],
):
    """
    front-end  -> socketio client (many different clients)
    webserver  -> socketio server (one/more replicas)
    payments   -> Sends messages to clients from external processes (one/more replicas)
    """

    # web server spy events
    server_connect = socketio_server_events["connect"]
    server_disconnect = socketio_server_events["disconnect"]
    server_on_check = socketio_server_events["on_check"]

    # client spy events
    client_on_payment = socketio_client_events["on_payment"]

    # checks
    assert server_connect.called
    assert not server_disconnect.called

    # client emits
    await socketio_client.emit("check", data="hoi")

    await _assert_called_once(server_on_check)

    # payment server emits
    await notify_payment()

    await _assert_called_once(client_on_payment)
