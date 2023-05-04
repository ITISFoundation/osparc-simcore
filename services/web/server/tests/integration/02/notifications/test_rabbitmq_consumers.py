# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from random import choice
from typing import Any, Awaitable, Callable
from unittest import mock

import aiopg
import aiopg.sa
import pytest
import socketio
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.users import UserID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_login import UserInfoDict
from redis import Redis
from servicelib.aiohttp.application import create_safe_application
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.diagnostics.plugin import setup_diagnostics
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.notifications.plugin import setup_notifications
from simcore_service_webserver.projects.plugin import setup_projects
from simcore_service_webserver.projects.project_models import ProjectDict
from simcore_service_webserver.resource_manager.plugin import setup_resource_manager
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio.events import SOCKET_IO_LOG_EVENT
from simcore_service_webserver.socketio.plugin import setup_socketio
from tenacity import RetryError
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_always, retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]

pytest_simcore_ops_services_selection = []


async def _assert_no_handler_not_called(handler: mock.Mock) -> None:
    with pytest.raises(RetryError):
        async for attempt in AsyncRetrying(
            retry=retry_always,
            stop=stop_after_delay(5),
            reraise=True,
            wait=wait_fixed(1),
        ):
            with attempt:
                print(
                    f"--> checking no mesage reached webclient... {attempt.retry_state.attempt_number} attempt"
                )
                handler.assert_not_called()


async def _assert_handler_called_with(
    handler: mock.Mock, expected_call: mock._Call
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            print(
                f"--> checking if messages reached webclient... {attempt.retry_state.attempt_number} attempt"
            )
            handler.assert_has_calls([expected_call])
            print(f"calls received! {attempt.retry_state.retry_object.statistics}")


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    app_config: dict[str, Any],
    rabbit_service: RabbitSettings,
    postgres_db: sa.engine.Engine,
    redis_client: Redis,
    monkeypatch_setenv_from_app_config: Callable,
) -> TestClient:
    app_config["storage"]["enabled"] = False

    monkeypatch_setenv_from_app_config(app_config)
    app = create_safe_application(app_config)

    assert setup_settings(app)

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_diagnostics(app)
    setup_login(app)
    setup_projects(app)
    setup_notifications(app)
    setup_director_v2(app)
    setup_socketio(app)
    setup_resource_manager(app)

    return event_loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={
                "port": app_config["main"]["port"],
                "host": app_config["main"]["host"],
            },
        )
    )


@pytest.fixture
async def rabbitmq_publisher(
    rabbitmq_client: Callable[[str], RabbitMQClient],
) -> RabbitMQClient:
    return rabbitmq_client("pytest_publisher")


_NON_ANONYMOUS_USER_ROLES = [u for u in UserRole if u is not UserRole.ANONYMOUS]


@pytest.mark.parametrize("user_role", _NON_ANONYMOUS_USER_ROLES, ids=str)
async def test_log_workflow(
    client: TestClient,
    rabbitmq_publisher: RabbitMQClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    faker: Faker,
    socketio_client_factory: Callable[
        [str | None, TestClient | None], Awaitable[socketio.AsyncClient]
    ],
    mocker: MockerFixture,
):
    """
    RabbitMQ --> Webserver --> webclient (socketio)

    """
    socket_io_conn = await socketio_client_factory(None, client)

    mock_log_handler = mocker.MagicMock()
    socket_io_conn.on(SOCKET_IO_LOG_EVENT, handler=mock_log_handler)

    random_node_id_in_project = NodeID(choice(list(user_project["workbench"])))
    log_message = LoggerRabbitMessage(
        user_id=UserID(logged_user["id"]),
        project_id=ProjectID(user_project["uuid"]),
        node_id=random_node_id_in_project,
        messages=[faker.text() for _ in range(10)],
    )
    await rabbitmq_publisher.publish(log_message.channel_name, log_message)

    expected_call = log_message.json(exclude={"user_id", "channel_name"})
    await _assert_handler_called_with(mock_log_handler, mock.call(expected_call))


@pytest.mark.parametrize("user_role", [UserRole.USER], ids=str)
async def test_log_workflow_blocks_if_project_is_hidden(
    client: TestClient,
    rabbitmq_publisher: RabbitMQClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    faker: Faker,
    socketio_client_factory: Callable[
        [str | None, TestClient | None], Awaitable[socketio.AsyncClient]
    ],
    mocker: MockerFixture,
    aiopg_engine: aiopg.sa.Engine,
):
    """
    RabbitMQ --> Webserver --> webclient (socketio)

    """
    socket_io_conn = await socketio_client_factory(None, client)
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            sa.update(projects)
            .values(hidden=True)
            .where(projects.c.uuid == user_project["uuid"])
        )

    mock_log_handler = mocker.MagicMock()
    socket_io_conn.on(SOCKET_IO_LOG_EVENT, handler=mock_log_handler)

    random_node_id_in_project = NodeID(choice(list(user_project["workbench"])))
    log_message = LoggerRabbitMessage(
        user_id=UserID(logged_user["id"]),
        project_id=ProjectID(user_project["uuid"]),
        node_id=random_node_id_in_project,
        messages=[faker.text() for _ in range(10)],
    )
    await rabbitmq_publisher.publish(log_message.channel_name, log_message)

    await _assert_no_handler_not_called(mock_log_handler)
