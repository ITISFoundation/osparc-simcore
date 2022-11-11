# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
import logging
from asyncio import sleep
from collections import namedtuple
from typing import Any, Awaitable, Callable, NamedTuple

import aio_pika
import pytest
import socketio
import sqlalchemy as sa
from faker.proxy import Faker
from models_library.basic_types import UUIDStr
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import (
    InstrumentationRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessage,
)
from models_library.users import UserID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.rabbit_service import RabbitExchanges
from servicelib.aiohttp.application import create_safe_application
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.comp_tasks import NodeClass
from simcore_service_webserver._constants import APP_SETTINGS_KEY
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.diagnostics import setup_diagnostics
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.projects.plugin import setup_projects
from simcore_service_webserver.resource_manager.plugin import setup_resource_manager
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio.plugin import setup_socketio
from tenacity import retry_if_exception_type
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "rabbit",
    "redis",
]

pytest_simcore_ops_services_selection = []


logger = logging.getLogger(__name__)

RabbitMessage = dict[str, Any]
LogMessages = list[LoggerRabbitMessage]
InstrumMessages = list[InstrumentationRabbitMessage]
ProgressMessages = list[ProgressRabbitMessage]


async def _publish_in_rabbit(
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    num_messages: int,
    rabbit_exchanges: RabbitExchanges,
) -> tuple[LogMessages, ProgressMessages, InstrumMessages]:

    log_messages = [
        LoggerRabbitMessage(
            user_id=user_id,
            project_id=project_id,
            node_id=node_uuid,
            messages=[f"log number {n}"],
        )
        for n in range(num_messages)
    ]
    progress_messages = [
        ProgressRabbitMessage(
            user_id=user_id,
            project_id=project_id,
            node_id=node_uuid,
            progress=float(n) / float(num_messages),
        )
        for n in range(num_messages)
    ]

    # indicate container is started
    instrumentation_start_message = (
        instrumentation_stop_message
    ) = InstrumentationRabbitMessage(
        metrics="service_started",
        user_id=user_id,
        project_id=project_id,
        node_id=node_uuid,
        service_uuid=node_uuid,
        service_type=NodeClass.COMPUTATIONAL,
        service_key="some/service/awesome/key",
        service_tag="some-awesome-tag",
    )
    instrumentation_stop_message.metrics = "service_stopped"
    instrumentation_stop_message.result = RunningState.SUCCESS
    instrumentation_messages = [
        instrumentation_start_message,
        instrumentation_stop_message,
    ]
    await rabbit_exchanges.instrumentation.publish(
        aio_pika.Message(
            body=instrumentation_start_message.json().encode(),
            content_type="text/json",
        ),
        routing_key="",
    )

    for n in range(num_messages):
        await rabbit_exchanges.logs.publish(
            aio_pika.Message(
                body=log_messages[n].json().encode(), content_type="text/json"
            ),
            routing_key="",
        )

        await rabbit_exchanges.progress.publish(
            aio_pika.Message(
                body=progress_messages[n].json().encode(), content_type="text/json"
            ),
            routing_key="",
        )

    # indicate container is stopped
    await rabbit_exchanges.instrumentation.publish(
        aio_pika.Message(
            body=instrumentation_stop_message.json().encode(),
            content_type="text/json",
        ),
        routing_key="",
    )

    return (log_messages, progress_messages, instrumentation_messages)


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    app_config: dict[str, Any],  ## waits until swarm with *_services are up
    rabbit_service: RabbitSettings,  ## waits until rabbit is responsive and set env vars
    postgres_db: sa.engine.Engine,
    mocker: MockerFixture,
    monkeypatch_setenv_from_app_config: Callable,
):
    app_config["storage"]["enabled"] = False

    monkeypatch_setenv_from_app_config(app_config)
    app = create_safe_application(app_config)

    assert setup_settings(app)
    assert app[APP_SETTINGS_KEY].WEBSERVER_COMPUTATION

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_diagnostics(app)
    setup_login(app)
    setup_projects(app)
    setup_computation(app)
    setup_director_v2(app)
    setup_socketio(app)
    setup_resource_manager(app)
    # GC not relevant for these test-suite,

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
def client_session_id(client_session_id_factory: Callable[[], str]) -> UUIDStr:
    return client_session_id_factory()


@pytest.fixture
def not_logged_user_id(faker: Faker, logged_user: dict[str, Any]) -> UserID:
    some_user_id = faker.pyint(min_value=logged_user["id"] + 1)
    assert logged_user["id"] != some_user_id
    return some_user_id


@pytest.fixture
def not_current_project_id(faker: Faker, user_project: dict[str, Any]) -> ProjectID:
    other_id = faker.uuid4(cast_to=None)
    assert (
        ProjectID(user_project["uuid"]) != other_id
    ), "bad luck... this should not happen very often though"
    return other_id


@pytest.fixture
def not_in_project_node_uuid(faker: Faker, user_project: dict[str, Any]) -> NodeID:
    not_in_project_node_uuid = faker.uuid4(cast_to=None)
    assert not any(
        NodeID(node_id) == not_in_project_node_uuid
        for node_id in user_project["workbench"]
    ), "bad luck... this should not happen very often though"
    return not_in_project_node_uuid


@pytest.fixture
async def socketio_subscriber_handlers(
    socketio_client_factory: Callable,
    client_session_id: UUIDStr,
    mocker: MockerFixture,
) -> NamedTuple:

    """socketio SUBSCRIBER

    Somehow this emulates the logic of the front-end:
    it connects to a session (client_session_id) and
    registers two event handlers that are be called
    when a message is received
    """
    # connect to websocket session
    # NOTE: will raise socketio.exceptions.ConnectionError: Unexpected status code 401 in server response
    # if client does not hold an authentication token
    sio: socketio.AsyncClient = await socketio_client_factory(client_session_id)

    WEBSOCKET_LOG_EVENTNAME = "logger"
    # called when log messages are received
    mock_log_handler = mocker.Mock()
    sio.on(WEBSOCKET_LOG_EVENTNAME, handler=mock_log_handler)

    WEBSOCKET_NODE_UPDATE_EVENTNAME = "nodeUpdated"
    # called when a node was updated (e.g. progress)
    mock_node_update_handler = mocker.Mock()
    sio.on(WEBSOCKET_NODE_UPDATE_EVENTNAME, handler=mock_node_update_handler)

    return namedtuple("_MockHandlers", "log_handler node_update_handler")(
        mock_log_handler, mock_node_update_handler
    )


@pytest.fixture
def publish_some_messages_in_rabbit(
    rabbit_exchanges: RabbitExchanges,
) -> Callable[
    [UserID, ProjectID, NodeID, int],
    Awaitable[tuple[LogMessages, ProgressMessages, InstrumMessages]],
]:
    """rabbitMQ PUBLISHER"""

    async def go(
        user_id: UserID,
        project_id: ProjectID,
        node_uuid: NodeID,
        num_messages: int,
    ):
        return await _publish_in_rabbit(
            user_id, project_id, node_uuid, num_messages, rabbit_exchanges
        )

    return go


@pytest.fixture
def user_role() -> UserRole:
    """provides a default when not override by paramtrization"""
    return UserRole.USER


#
#   publisher ---> (rabbitMQ)  ---> webserver --- (socketio) ---> front-end pages
#
# - logs, instrumentation and progress are set to rabbitMQ messages
# - webserver consumes these messages and forwards them to the front-end broadcasting them to socketio
# - all front-end insteances connected to these channes will get notified when new messages are directed
#   to them
#

POLLING_TIME = 0.2
TIMEOUT_S = 10
RETRY_POLICY = dict(
    wait=wait_fixed(POLLING_TIME),
    stop=stop_after_delay(TIMEOUT_S),
    before_sleep=before_sleep_log(logger, log_level=logging.WARNING),
    retry=retry_if_exception_type(AssertionError),
    reraise=True,
)
NUMBER_OF_MESSAGES = 1
USER_ROLES = [
    UserRole.GUEST,
    UserRole.USER,
    UserRole.TESTER,
]


@pytest.mark.parametrize("user_role", USER_ROLES)
async def test_publish_to_other_user(
    not_logged_user_id: UserID,
    not_current_project_id: ProjectID,
    not_in_project_node_uuid: NodeID,
    #
    socketio_subscriber_handlers: NamedTuple,
    publish_some_messages_in_rabbit: Callable[
        [UserID, ProjectID, NodeID, int],
        Awaitable[tuple[LogMessages, ProgressMessages, InstrumMessages]],
    ],
):
    mock_log_handler, mock_node_update_handler = socketio_subscriber_handlers

    # Some other client publishes messages with wrong user id
    await publish_some_messages_in_rabbit(
        not_logged_user_id,
        not_current_project_id,
        not_in_project_node_uuid,
        NUMBER_OF_MESSAGES,
    )
    await sleep(TIMEOUT_S)

    mock_log_handler.assert_not_called()
    mock_node_update_handler.assert_not_called()


@pytest.mark.parametrize("user_role", USER_ROLES)
async def test_publish_to_user(
    logged_user: UserInfoDict,
    not_current_project_id: ProjectID,
    not_in_project_node_uuid: NodeID,
    #
    socketio_subscriber_handlers: NamedTuple,
    publish_some_messages_in_rabbit: Callable[
        [UserID, ProjectID, NodeID, int],
        Awaitable[tuple[LogMessages, ProgressMessages, InstrumMessages]],
    ],
):
    mock_log_handler, mock_node_update_handler = socketio_subscriber_handlers

    # publish messages with correct user id, but no project
    log_messages, _, _ = await publish_some_messages_in_rabbit(
        logged_user["id"],
        not_current_project_id,
        not_in_project_node_uuid,
        NUMBER_OF_MESSAGES,
    )

    async for attempt in AsyncRetrying(**RETRY_POLICY):
        with attempt:
            assert mock_log_handler.call_count == (NUMBER_OF_MESSAGES)

    for mock_call, expected_message in zip(
        mock_log_handler.call_args_list, log_messages
    ):
        value = mock_call[0]
        deserialized_value = json.loads(value[0])
        assert deserialized_value == json.loads(
            expected_message.json(exclude={"user_id"})
        )
    mock_node_update_handler.assert_not_called()


@pytest.mark.parametrize("user_role", USER_ROLES)
async def test_publish_about_users_project(
    logged_user: UserInfoDict,
    user_project: dict[str, Any],
    not_in_project_node_uuid: NodeID,
    #
    socketio_subscriber_handlers: NamedTuple,
    publish_some_messages_in_rabbit: Callable[
        [UserID, ProjectID, NodeID, int],
        Awaitable[tuple[LogMessages, ProgressMessages, InstrumMessages]],
    ],
):
    mock_log_handler, mock_node_update_handler = socketio_subscriber_handlers

    # publish message with correct user id, project but not node
    log_messages, _, _ = await publish_some_messages_in_rabbit(
        UserID(logged_user["id"]),
        ProjectID(user_project["uuid"]),
        not_in_project_node_uuid,
        NUMBER_OF_MESSAGES,
    )

    async for attempt in AsyncRetrying(**RETRY_POLICY):
        with attempt:
            assert mock_log_handler.call_count == (NUMBER_OF_MESSAGES)

    for mock_call, expected_message in zip(
        mock_log_handler.call_args_list, log_messages
    ):
        value = mock_call[0]
        deserialized_value = json.loads(value[0])
        assert deserialized_value == json.loads(
            expected_message.json(exclude={"user_id"})
        )
    mock_node_update_handler.assert_not_called()


@pytest.mark.parametrize("user_role", USER_ROLES)
async def test_publish_about_users_projects_node(
    logged_user: UserInfoDict,
    user_project: dict[str, Any],
    #
    socketio_subscriber_handlers: NamedTuple,
    publish_some_messages_in_rabbit: Callable[
        [UserID, ProjectID, NodeID, int],
        Awaitable[tuple[LogMessages, ProgressMessages, InstrumMessages]],
    ],
):
    mock_log_handler, mock_node_update_handler = socketio_subscriber_handlers

    # publish message with correct user id, project node
    node_uuid = NodeID(list(user_project["workbench"])[0])
    log_messages, _, _ = await publish_some_messages_in_rabbit(
        UserID(logged_user["id"]),
        ProjectID(user_project["uuid"]),
        node_uuid,
        NUMBER_OF_MESSAGES,
    )

    async for attempt in AsyncRetrying(**RETRY_POLICY):
        with attempt:
            assert mock_log_handler.call_count == (NUMBER_OF_MESSAGES)
            assert mock_node_update_handler.call_count == (NUMBER_OF_MESSAGES)

    for mock_call, expected_message in zip(
        mock_log_handler.call_args_list, log_messages
    ):
        value = mock_call[0]
        deserialized_value = json.loads(value[0])
        assert deserialized_value == json.loads(
            expected_message.json(exclude={"user_id"})
        )

    # mock_log_handler.assert_has_calls(log_calls, any_order=True)
    mock_node_update_handler.assert_called()
    assert mock_node_update_handler.call_count == (NUMBER_OF_MESSAGES)
