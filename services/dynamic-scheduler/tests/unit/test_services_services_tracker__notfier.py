# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections.abc import AsyncIterable, AsyncIterator, Callable
from contextlib import (
    AsyncExitStack,
    _AsyncGeneratorContextManager,
    asynccontextmanager,
)
from unittest.mock import AsyncMock

import pytest
import socketio
from faker import Faker
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_directorv2.dynamic_services_utils import (
    get_service_status_serialization_options,
)
from models_library.api_schemas_dynamic_scheduler.socketio import (
    SOCKET_IO_SERVICE_STATUS_EVENT,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.users import UserID
from pydantic import NonNegativeInt, parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.utils import logged_gather
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.core.settings import ApplicationSettings
from simcore_service_dynamic_scheduler.services.services_tracker._notifier._core import (
    publish_message,
)
from simcore_service_dynamic_scheduler.services.services_tracker.api import (
    ServicesTracker,
    get_services_tracker,
)
from socketio import AsyncServer
from tenacity import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
    rabbit_service: RabbitSettings,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def services_tracker(app: FastAPI) -> AsyncIterable[ServicesTracker]:
    tracker = get_services_tracker(app)
    yield tracker
    # cleanup distributed cache between tests to avoid flakiness
    await tracker.service_status_cache.clear()


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint()


@pytest.fixture
async def socketio_server(
    app: FastAPI,
    socketio_server_factory: Callable[
        [RabbitSettings], _AsyncGeneratorContextManager[AsyncServer]
    ],
) -> AsyncIterable[AsyncServer]:
    # Same configuration as simcore_service_webserver/socketio/server.py
    app_settings: ApplicationSettings = app.state.settings
    rabbit_settings = app_settings.DYNAMIC_SCHEDULER_RABBITMQ

    assert rabbit_settings

    async with socketio_server_factory(rabbit_settings) as server:
        yield server


@pytest.fixture
def room_name(user_id: UserID) -> SocketIORoomStr:
    return SocketIORoomStr.from_user_id(user_id)


@asynccontextmanager
async def get_socketio_client(server_url: str) -> AsyncIterator[socketio.AsyncClient]:
    """This emulates a socketio client in the front-end"""
    client = socketio.AsyncClient(logger=True, engineio_logger=True)
    await client.connect(f"{server_url}", transports=["websocket"])

    yield client

    await client.disconnect()


def _get_on_service_status_event(socketio_client: socketio.AsyncClient) -> AsyncMock:
    # emulates front-end receiving message

    async def on_service_status(data):
        assert parse_obj_as(NodeGet | DynamicServiceGet | NodeGetIdle, data) is not None

    on_event_spy = AsyncMock(wraps=on_service_status)
    socketio_client.on(SOCKET_IO_SERVICE_STATUS_EVENT, on_event_spy)

    return on_event_spy


async def _assert_call_count(mock: AsyncMock, *, call_count: int) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1), stop=stop_after_attempt(5), reraise=True
    ):
        with attempt:
            assert mock.call_count == call_count


@pytest.mark.parametrize(
    "service_status",
    [
        DynamicServiceGet.parse_obj(
            DynamicServiceGet.Config.schema_extra["examples"][0]
        ),
        NodeGet.parse_obj(NodeGet.Config.schema_extra["example"]),
        NodeGetIdle.parse_obj(NodeGetIdle.Config.schema_extra["example"]),
    ],
)
async def test_notifier_publish_message(
    services_tracker: ServicesTracker,
    socketio_server_events: dict[str, AsyncMock],
    server_url: str,
    app: FastAPI,
    faker: Faker,
    user_id: UserID,
    service_status: NodeGet | DynamicServiceGet | NodeGetIdle,
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
        on_service_status_events: list[AsyncMock] = [
            _get_on_service_status_event(c) for c in frontend_clients
        ]

        # server publishes a message
        await publish_message(
            app,
            node_id=faker.uuid4(cast_to=None),
            service_status=service_status,
            user_id=user_id,
        )

        # check that all clients received it
        for on_service_status_event in on_service_status_events:
            await _assert_call_count(on_service_status_event, call_count=1)
            on_service_status_event.assert_awaited_once_with(
                jsonable_encoder(
                    service_status,
                    **get_service_status_serialization_options(service_status),
                )
            )

    await _assert_call_count(server_disconnect, call_count=number_of_clients)
