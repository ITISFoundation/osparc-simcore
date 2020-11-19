# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
import json
import time
from asyncio import sleep
from typing import Any, Callable, Dict, Tuple
from uuid import uuid4

import aio_pika
import pytest
import sqlalchemy as sa
from mock import call
from models_library.settings.rabbit import RabbitConfig
from servicelib.application import create_safe_application
from servicelib.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.computation_config import CONFIG_SECTION_NAME
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.resource_manager import setup_resource_manager
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio import setup_socketio

API_VERSION = "v0"

# Selection of core and tool services started in this swarm fixture (integration)
core_services = ["postgres", "redis", "rabbit"]

ops_services = []


@pytest.fixture
def client(
    loop,
    aiohttp_client,
    app_config,  ## waits until swarm with *_services are up
    rabbit_service: RabbitConfig,  ## waits until rabbit is responsive
    postgres_db: sa.engine.Engine,
):
    assert app_config["rest"]["version"] == API_VERSION

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


# ------------------------------------------


def _create_rabbit_message(
    message_name: str, node_uuid: str, user_id: str, project_id: str, param: Any
) -> Dict:
    message = {
        "Channel": message_name.title(),
        "Node": node_uuid,
        "user_id": user_id,
        "project_id": project_id,
    }

    if message_name == "log":
        message["Messages"] = param
    if message_name == "progress":
        message["Progress"] = param
    return message


@pytest.fixture
def client_session_id() -> str:
    return str(uuid4())


async def _publish_messages(
    num_messages: int,
    node_uuid: str,
    user_id: str,
    project_id: str,
    rabbit_exchange: Tuple[aio_pika.Exchange, aio_pika.Exchange],
) -> Tuple[Dict, Dict, Dict]:
    log_messages = [
        _create_rabbit_message("log", node_uuid, user_id, project_id, f"log number {n}")
        for n in range(num_messages)
    ]
    progress_messages = [
        _create_rabbit_message(
            "progress", node_uuid, user_id, project_id, n / num_messages
        )
        for n in range(num_messages)
    ]
    # send the messages over rabbit
    logs_exchange, instrumentation_exchange = rabbit_exchange

    # indicate container is started
    instrumentation_start_message = instrumentation_stop_message = {
        "metrics": "service_started",
        "user_id": user_id,
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


async def _wait_until(pred: Callable, timeout: int):
    max_wait_time = time.time() + timeout
    while time.time() < max_wait_time:
        if pred():
            return
        await sleep(1)
    pytest.fail("waited too long for getting websockets events")


@pytest.mark.parametrize(
    "user_role",
    [
        (UserRole.GUEST),
        (UserRole.USER),
        (UserRole.TESTER),
    ],
)
async def test_rabbit_websocket_computation(
    director_v2_subsystem_mock,
    mock_orphaned_services,
    logged_user,
    user_project,
    socketio_client,
    client_session_id: str,
    mocker,
    rabbit_exchange: Tuple[aio_pika.Exchange, aio_pika.Exchange],
    node_uuid: str,
    user_id: str,
    project_id: str,
):

    # corresponding websocket event names
    websocket_log_event = "logger"
    websocket_node_update_event = "nodeUpdated"
    # connect websocket
    sio = await socketio_client(client_session_id)
    # register mock websocket handler functions
    mock_log_handler_fct = mocker.Mock()
    mock_node_update_handler_fct = mocker.Mock()
    sio.on(websocket_log_event, handler=mock_log_handler_fct)
    sio.on(websocket_node_update_event, handler=mock_node_update_handler_fct)
    # publish messages with wrong user id
    NUMBER_OF_MESSAGES = 1
    TIMEOUT_S = 20

    await _publish_messages(
        NUMBER_OF_MESSAGES, node_uuid, user_id, project_id, rabbit_exchange
    )
    await sleep(1)
    mock_log_handler_fct.assert_not_called()
    mock_node_update_handler_fct.assert_not_called()

    # publish messages with correct user id, but no project
    log_messages, _, _ = await _publish_messages(
        NUMBER_OF_MESSAGES, node_uuid, logged_user["id"], project_id, rabbit_exchange
    )

    def predicate() -> bool:
        return mock_log_handler_fct.call_count == (NUMBER_OF_MESSAGES)

    await _wait_until(predicate, TIMEOUT_S)
    log_calls = [call(json.dumps(message)) for message in log_messages]
    mock_log_handler_fct.assert_has_calls(log_calls, any_order=True)
    mock_node_update_handler_fct.assert_not_called()
    # publish message with correct user id, project but not node
    mock_log_handler_fct.reset_mock()
    log_messages, _, _ = await _publish_messages(
        NUMBER_OF_MESSAGES,
        node_uuid,
        logged_user["id"],
        user_project["uuid"],
        rabbit_exchange,
    )
    await _wait_until(predicate, TIMEOUT_S)
    log_calls = [call(json.dumps(message)) for message in log_messages]
    mock_log_handler_fct.assert_has_calls(log_calls, any_order=True)
    mock_node_update_handler_fct.assert_not_called()
    mock_log_handler_fct.reset_mock()

    # publish message with correct user id, project node
    mock_log_handler_fct.reset_mock()
    node_uuid = list(user_project["workbench"])[0]
    log_messages, _, _ = await _publish_messages(
        NUMBER_OF_MESSAGES,
        node_uuid,
        logged_user["id"],
        user_project["uuid"],
        rabbit_exchange,
    )

    def predicate2() -> bool:
        return mock_log_handler_fct.call_count == (
            NUMBER_OF_MESSAGES
        ) and mock_node_update_handler_fct.call_count == (NUMBER_OF_MESSAGES)

    await _wait_until(predicate2, TIMEOUT_S)
    log_calls = [call(json.dumps(message)) for message in log_messages]
    mock_log_handler_fct.assert_has_calls(log_calls, any_order=True)
    mock_node_update_handler_fct.assert_called()
    assert mock_node_update_handler_fct.call_count == (NUMBER_OF_MESSAGES)
