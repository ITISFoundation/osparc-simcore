# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections.abc import AsyncIterable, Callable
from contextlib import AsyncExitStack, _AsyncGeneratorContextManager
from unittest.mock import AsyncMock

import pytest
import socketio
from faker import Faker
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_directorv2.notifications import ServiceNoMoreCredits
from models_library.api_schemas_directorv2.socketio import (
    SOCKET_IO_SERVICE_NO_MORE_CREDITS_EVENT,
)
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import NonNegativeInt
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.utils import logged_gather
from settings_library.rabbit import RabbitSettings
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.modules.notifier import (
    publish_shutdown_no_more_credits,
)
from socketio import AsyncServer
from tenacity import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def disable_modules_setup(mock_exclusive: None, mocker: MockerFixture) -> None:
    module_base = "simcore_service_director_v2.core.application"
    mocker.patch(f"{module_base}.db.setup", autospec=True, return_value=False)
    mocker.patch(
        f"{module_base}.resource_usage_tracker_client.setup",
        autospec=True,
        return_value=False,
    )


@pytest.fixture
def mock_env(
    disable_modules_setup: None,
    monkeypatch: pytest.MonkeyPatch,
    mock_env: EnvVarsDict,
    rabbit_service: RabbitSettings,
    faker: Faker,
) -> EnvVarsDict:
    setenvs_from_dict(
        monkeypatch,
        {
            "S3_ENDPOINT": faker.url(),
            "S3_ACCESS_KEY": faker.pystr(),
            "S3_REGION": faker.pystr(),
            "S3_SECRET_KEY": faker.pystr(),
            "S3_BUCKET_NAME": faker.pystr(),
            "DIRECTOR_ENABLED": "0",
            "DIRECTOR_V0_ENABLED": "0",
            "DIRECTOR_V2_CATALOG": "null",
            "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED": "0",
            "COMPUTATIONAL_BACKEND_ENABLED": "0",
            "DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED": "1",
        },
    )
    return mock_env


@pytest.fixture
async def socketio_server(
    initialized_app: FastAPI,
    socketio_server_factory: Callable[
        [RabbitSettings], _AsyncGeneratorContextManager[AsyncServer]
    ],
) -> AsyncIterable[AsyncServer]:
    # Same configuration as simcore_service_webserver/socketio/server.py
    settings: AppSettings = initialized_app.state.settings
    assert settings.DIRECTOR_V2_RABBITMQ

    async with socketio_server_factory(settings.DIRECTOR_V2_RABBITMQ) as server:
        yield server


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def room_name(user_id: UserID) -> SocketIORoomStr:
    return SocketIORoomStr.from_user_id(user_id)


@pytest.fixture
def wallet_id(faker: Faker) -> WalletID:
    return faker.pyint()


def _get_on_no_more_credits_event(
    socketio_client: socketio.AsyncClient,
) -> AsyncMock:
    # emulates front-end receiving message

    async def on_no_more_credits(data):
        assert ServiceNoMoreCredits.model_validate(data) is not None

    on_event_spy = AsyncMock(wraps=on_no_more_credits)
    socketio_client.on(SOCKET_IO_SERVICE_NO_MORE_CREDITS_EVENT, on_event_spy)

    return on_event_spy


async def _assert_call_count(mock: AsyncMock, *, call_count: int) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1), stop=stop_after_attempt(500), reraise=True
    ):
        with attempt:
            assert mock.call_count == call_count


async def test_notifier_publish_message(
    socketio_server_events: dict[str, AsyncMock],
    initialized_app: FastAPI,
    user_id: UserID,
    node_id: NodeID,
    wallet_id: WalletID,
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
        no_no_more_credits_events: list[AsyncMock] = [
            _get_on_no_more_credits_event(c) for c in frontend_clients
        ]

        # server publishes a message
        await publish_shutdown_no_more_credits(
            initialized_app, user_id=user_id, node_id=node_id, wallet_id=wallet_id
        )

        # check that all clients received it
        for on_no_more_credits_event in no_no_more_credits_events:
            await _assert_call_count(on_no_more_credits_event, call_count=1)
            on_no_more_credits_event.assert_awaited_once_with(
                jsonable_encoder(
                    ServiceNoMoreCredits(node_id=node_id, wallet_id=wallet_id)
                )
            )

    await _assert_call_count(server_disconnect, call_count=number_of_clients)
