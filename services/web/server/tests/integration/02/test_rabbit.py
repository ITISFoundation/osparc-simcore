# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import logging
from asyncio import sleep
from collections import namedtuple
from typing import Any, Callable, Dict, List, NamedTuple, Tuple
from unittest.mock import call
from uuid import uuid4

import aio_pika
import pytest
import socketio
import sqlalchemy as sa
from models_library.settings.rabbit import RabbitConfig
from pytest_mock import MockerFixture
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.login.module_setup import setup_login
from simcore_service_webserver.projects.module_setup import setup_projects
from simcore_service_webserver.resource_manager.module_setup import (
    setup_resource_manager,
)
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio.module_setup import setup_socketio
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


# HELPERS ------------------------------------------------------------------------------------

logger = logging.getLogger(__name__)

UUIDStr = str

RabbitMessage = Dict[str, Any]
LogMessages = List[RabbitMessage]
InstrumMessages = List[RabbitMessage]
ProgressMessages = List[RabbitMessage]


async def _publish_in_rabbit(
    user_id: int,
    project_id: UUIDStr,
    node_uuid: UUIDStr,
    num_messages: int,
    rabbit_exchange: Tuple[aio_pika.Exchange, aio_pika.Exchange],
) -> Tuple[LogMessages, ProgressMessages, InstrumMessages]:
    def _msg(
        message_name: str, node_uuid: str, user_id: int, project_id: str, param: Any
    ) -> RabbitMessage:
        message = {
            "channel": message_name,
            "node_id": node_uuid,
            "user_id": f"{user_id}",
            "project_id": project_id,
        }

        if message_name == "log":
            message["messages"] = param
        if message_name == "progress":
            message["progress"] = param

        return message

    # -----

    log_messages = [
        _msg("logger", node_uuid, user_id, project_id, f"log number {n}")
        for n in range(num_messages)
    ]
    progress_messages = [
        _msg("progress", node_uuid, user_id, project_id, n / num_messages)
        for n in range(num_messages)
    ]
    # send the messages over rabbit
    logs_exchange, instrumentation_exchange = rabbit_exchange

    # indicate container is started
    instrumentation_start_message = instrumentation_stop_message = {
        "metrics": "service_started",
        "user_id": f"{user_id}",
        "project_id": project_id,
        "service_uuid": node_uuid,
        "service_type": "COMPUTATIONAL",
        "service_key": "some/service/awesome/key",
        "service_tag": "some-awesome-tag",
    }
    instrumentation_stop_message["metrics"] = "service_stopped"
    instrumentation_stop_message["result"] = "SUCCESS"
    instrumentation_messages = [
        instrumentation_start_message,
        instrumentation_stop_message,
    ]
    await instrumentation_exchange.publish(
        aio_pika.Message(
            body=json.dumps(instrumentation_start_message).encode(),
            content_type="text/json",
        ),
        routing_key="",
    )

    for n in range(num_messages):
        await logs_exchange.publish(
            aio_pika.Message(
                body=json.dumps(log_messages[n]).encode(), content_type="text/json"
            ),
            routing_key="",
        )

        await logs_exchange.publish(
            aio_pika.Message(
                body=json.dumps(progress_messages[n]).encode(), content_type="text/json"
            ),
            routing_key="",
        )

    # indicate container is stopped
    await instrumentation_exchange.publish(
        aio_pika.Message(
            body=json.dumps(instrumentation_stop_message).encode(),
            content_type="text/json",
        ),
        routing_key="",
    )

    return (log_messages, progress_messages, instrumentation_messages)


# FIXTURES ------------------------------------------------------------------------------------


@pytest.fixture
def client(
    loop,
    aiohttp_client,
    app_config,  ## waits until swarm with *_services are up
    rabbit_service: RabbitConfig,  ## waits until rabbit is responsive and set env vars
    postgres_db: sa.engine.Engine,
    mocker,
):
    app_config["storage"]["enabled"] = False

    # fake config
    app = create_safe_application()
    app[APP_CONFIG_KEY] = app_config

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_projects(app)
    setup_computation(app)
    setup_director_v2(app)
    setup_socketio(app)

    # GC not relevant for these test-suite,
    mocker.patch(
        "simcore_service_webserver.resource_manager.module_setup.setup_garbage_collector",
        side_effect=lambda app: print(
            f"PATCH @{__name__}:"
            "Garbage collector disabled."
            "Mock bypasses setup_garbage_collector to skip initializing the GC"
        ),
    )
    setup_resource_manager(app)

    yield loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={
                "port": app_config["main"]["port"],
                "host": app_config["main"]["host"],
            },
        )
    )


@pytest.fixture
def client_session_id() -> UUIDStr:
    return str(uuid4())


@pytest.fixture
def other_user_id(user_id, logged_user):
    other = user_id
    assert logged_user["id"] != other
    return other


@pytest.fixture
def other_project_id(project_id, user_project):
    other = project_id
    assert user_project["uuid"] != other
    return other


@pytest.fixture
def other_node_uuid(node_uuid, user_project):
    other = node_uuid
    node_uuid = list(user_project["workbench"])[0]
    assert node_uuid != other
    return other


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
    rabbit_exchange: Tuple[aio_pika.Exchange, aio_pika.Exchange],
) -> Callable:
    """rabbitMQ PUBLISHER"""

    async def go(
        user_id: int,
        project_id: str,
        node_uuid: str,
        num_messages: int,
    ):
        return await _publish_in_rabbit(
            user_id, project_id, node_uuid, num_messages, rabbit_exchange
        )

    return go


@pytest.fixture
def user_role():
    """provides a default when not override by paramtrization"""
    return UserRole.USER


# TESTS ------------------------------------------------------------------------------------
#
#   publisher ---> (rabbitMQ)  ---> webserver --- (socketio) ---> front-end pages
#
# - logs, instrumentation and progress are set to rabbitMQ messages
# - webserver consumes these messages and forwards them to the front-end broadcasting them to socketio
# - all front-end insteances connected to these channes will get notified when new messages are directed
#   to them
#

POLLING_TIME = 0.2
TIMEOUT_S = 1
RETRY_POLICY = dict(
    wait=wait_fixed(POLLING_TIME),
    stop=stop_after_delay(TIMEOUT_S),
    before_sleep=before_sleep_log(logger, log_level=logging.WARNING),
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
    other_user_id,
    other_project_id,
    other_node_uuid,
    #
    socketio_subscriber_handlers,
    publish_some_messages_in_rabbit,
):
    mock_log_handler, mock_node_update_handler = socketio_subscriber_handlers

    # Some other client publishes messages with wrong user id
    await publish_some_messages_in_rabbit(
        other_user_id,
        other_project_id,
        other_node_uuid,
        NUMBER_OF_MESSAGES,
    )
    await sleep(TIMEOUT_S)

    mock_log_handler.assert_not_called()
    mock_node_update_handler.assert_not_called()


@pytest.mark.parametrize("user_role", USER_ROLES)
async def test_publish_to_user(
    logged_user: Dict[str, Any],
    other_project_id,
    other_node_uuid,
    #
    socketio_subscriber_handlers,
    publish_some_messages_in_rabbit,
):
    mock_log_handler, mock_node_update_handler = socketio_subscriber_handlers

    # publish messages with correct user id, but no project
    log_messages, _, _ = await publish_some_messages_in_rabbit(
        logged_user["id"],
        other_project_id,
        other_node_uuid,
        NUMBER_OF_MESSAGES,
    )

    async for attempt in AsyncRetrying(**RETRY_POLICY):
        with attempt:
            assert mock_log_handler.call_count == (NUMBER_OF_MESSAGES)

    log_calls = [call(json.dumps(message)) for message in log_messages]
    mock_log_handler.assert_has_calls(log_calls, any_order=True)
    mock_node_update_handler.assert_not_called()


@pytest.mark.parametrize("user_role", USER_ROLES)
async def test_publish_about_users_project(
    logged_user: Dict[str, Any],
    user_project: Dict[str, Any],
    other_node_uuid,
    #
    socketio_subscriber_handlers,
    publish_some_messages_in_rabbit,
):
    mock_log_handler, mock_node_update_handler = socketio_subscriber_handlers

    # publish message with correct user id, project but not node
    log_messages, _, _ = await publish_some_messages_in_rabbit(
        logged_user["id"],
        user_project["uuid"],
        other_node_uuid,
        NUMBER_OF_MESSAGES,
    )

    async for attempt in AsyncRetrying(**RETRY_POLICY):
        with attempt:
            assert mock_log_handler.call_count == (NUMBER_OF_MESSAGES)

    log_calls = [call(json.dumps(message)) for message in log_messages]
    mock_log_handler.assert_has_calls(log_calls, any_order=True)
    mock_node_update_handler.assert_not_called()


@pytest.mark.parametrize("user_role", USER_ROLES)
async def test_publish_about_users_projects_node(
    logged_user: Dict[str, Any],
    user_project: Dict[str, Any],
    #
    socketio_subscriber_handlers,
    publish_some_messages_in_rabbit,
):
    mock_log_handler, mock_node_update_handler = socketio_subscriber_handlers

    # publish message with correct user id, project node
    node_uuid = list(user_project["workbench"])[0]
    log_messages, _, _ = await publish_some_messages_in_rabbit(
        logged_user["id"],
        user_project["uuid"],
        node_uuid,
        NUMBER_OF_MESSAGES,
    )

    async for attempt in AsyncRetrying(**RETRY_POLICY):
        with attempt:
            assert mock_log_handler.call_count == (NUMBER_OF_MESSAGES)
            assert mock_node_update_handler.call_count == (NUMBER_OF_MESSAGES)

    log_calls = [call(json.dumps(message)) for message in log_messages]
    mock_log_handler.assert_has_calls(log_calls, any_order=True)
    mock_node_update_handler.assert_called()
    assert mock_node_update_handler.call_count == (NUMBER_OF_MESSAGES)


@pytest.mark.skip(reason="DEV")
def test_engineio_pending_tasks(logged_user, socketio_subscriber_handlers):
    #
    # This tests passes but reproduces these logs at the end
    #
    #
    # ERROR: asyncio:Task was destroyed but it is pending!
    # task: <Task pending name='Task-90' coro=<AsyncServer._service_task() running at engineio/asyncio_server.py:491>
    # wait_for=<Future pending cb=[<TaskWakeupMethWrapper object >()]>>
    #  ...
    #
    # FIXME: AsyncServer does not exit cleanly
    # SEE https://github.com/miguelgrinberg/python-socketio/issues/378

    socketio_subscriber_handlers.mock_log_handler.assert_not_called()
    socketio_subscriber_handlers.mock_node_update_handler.assert_not_called()
