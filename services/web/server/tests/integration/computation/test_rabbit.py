# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import time
from asyncio import sleep
from typing import Any, Callable, Dict, Tuple
from uuid import uuid4

import aio_pika
import pytest
from mock import call

from servicelib.application import create_safe_application
from servicelib.application_keys import APP_CONFIG_KEY
from simcore_sdk.config.rabbit import eval_broker
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.computation_config import CONFIG_SECTION_NAME
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.resource_manager import setup_resource_manager
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio import setup_sockets

API_VERSION = "v0"

# Selection of core and tool services started in this swarm fixture (integration)
core_services = [
    'postgres',
    'redis',
    'rabbit'
]

ops_services = [
]

@pytest.fixture
def client(loop, aiohttp_client,
        app_config,    ## waits until swarm with *_services are up
        rabbit_service ## waits until rabbit is responsive
    ):
    assert app_config["rest"]["version"] == API_VERSION

    app_config['storage']['enabled'] = False
    app_config["db"]["init_tables"] = True # inits postgres_service

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
    setup_sockets(app)
    setup_resource_manager(app)

    yield loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': app_config["main"]["port"],
        'host': app_config['main']['host']
    }))

@pytest.fixture
def rabbit_config(app_config):
    rb_config = app_config[CONFIG_SECTION_NAME]
    yield rb_config

@pytest.fixture
def rabbit_broker(rabbit_config):
    rabbit_broker = eval_broker(rabbit_config)
    yield rabbit_broker

@pytest.fixture
async def pika_connection(loop, rabbit_broker):
    connection = await aio_pika.connect(rabbit_broker, ssl=True, connection_attempts=100)
    yield connection
    await connection.close()

# ------------------------------------------

@pytest.fixture
async def rabbit_channels(loop, pika_connection, rabbit_config: Dict) -> Dict[str, aio_pika.Exchange]:
    async def create(channel_name: str) -> aio_pika.Exchange:
        # create rabbit pika exchange channel
        channel = await pika_connection.channel()
        pika_channel = rabbit_config["channels"][channel_name]
        pika_exchange = await channel.declare_exchange(
            pika_channel, aio_pika.ExchangeType.FANOUT,
            auto_delete=True
        )
        return pika_exchange

    return {
        "log": await create("log"),
        "progress": await create("progress")
    }


def _create_rabbit_message(message_name: str, node_uuid: str, user_id: str, project_id: str, param: Any) -> Dict:
    message = {
        "Channel":message_name.title(),
        "Node": node_uuid,
        "user_id": user_id,
        "project_id": project_id
    }

    if message_name == "log":
        message["Messages"] = param
    if message_name == "progress":
        message["Progress"] = param
    return message

@pytest.fixture
def client_session_id():
    return str(uuid4())


async def _publish_messages(num_messages: int, node_uuid: str, user_id: str, project_id: str, rabbit_channels: Dict[str, aio_pika.Exchange]) -> Tuple[Dict, Dict, Dict]:
    log_messages = [_create_rabbit_message("log", node_uuid, user_id, project_id, f"log number {n}") for n in range(num_messages)]
    progress_messages = [_create_rabbit_message("progress", node_uuid, user_id, project_id, n/num_messages) for n in range(num_messages)]
    final_log_message = _create_rabbit_message("log", node_uuid, user_id, project_id, f"...postprocessing end")

    # send the messages over rabbit
    for n in range(num_messages):
        await rabbit_channels["log"].publish(
            aio_pika.Message(
                body=json.dumps(log_messages[n]).encode(),
                content_type="text/json"), routing_key = ""
        )
        await rabbit_channels["progress"].publish(
            aio_pika.Message(
                body=json.dumps(progress_messages[n]).encode(),
                content_type="text/json"), routing_key = ""
        )
    await rabbit_channels["log"].publish(
        aio_pika.Message(
            body=json.dumps(final_log_message).encode(),
            content_type="text/json"), routing_key = ""
    )

    return (log_messages, progress_messages, final_log_message)


async def _wait_until(fct: Callable, timeout: int):
    max_wait_time = time.time() + timeout
    while time.time() < max_wait_time:
        if fct():
            break
        await sleep(0.1)

@pytest.mark.parametrize("user_role", [
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_rabbit_websocket_computation(loop, logged_user, user_project,
                                            socketio_client, client_session_id, mocker,
                                            rabbit_channels, node_uuid, user_id, project_id):

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
    NUMBER_OF_MESSAGES = 100
    TIMEOUT_S = 5

    await _publish_messages(NUMBER_OF_MESSAGES, node_uuid, user_id, project_id, rabbit_channels)
    await sleep(1)
    mock_log_handler_fct.assert_not_called()
    mock_node_update_handler_fct.assert_not_called()

    # publish messages with correct user id, but no project
    log_messages, _, _ = await _publish_messages(NUMBER_OF_MESSAGES, node_uuid, logged_user["id"], project_id, rabbit_channels)
    def predicate() -> bool:
        return mock_log_handler_fct.call_count == (NUMBER_OF_MESSAGES+1)
    await _wait_until(predicate, TIMEOUT_S)
    # await sleep(WAIT_FOR_MESSAGES_S)
    log_calls = [call(json.dumps(message)) for message in log_messages]
    mock_log_handler_fct.assert_has_calls(log_calls, any_order=True)
    mock_node_update_handler_fct.assert_not_called()
    # publish message with correct user id, project but not node
    mock_log_handler_fct.reset_mock()
    log_messages, _, _ = await _publish_messages(NUMBER_OF_MESSAGES, node_uuid, logged_user["id"], user_project["uuid"], rabbit_channels)
    await _wait_until(predicate, TIMEOUT_S)
    log_calls = [call(json.dumps(message)) for message in log_messages]
    mock_log_handler_fct.assert_has_calls(log_calls, any_order=True)
    mock_node_update_handler_fct.assert_not_called()
    mock_log_handler_fct.reset_mock()

    # publish message with correct user id, project node
    mock_log_handler_fct.reset_mock()
    node_uuid = list(user_project["workbench"])[0]
    log_messages, progress_messages, final_log_message = await _publish_messages(NUMBER_OF_MESSAGES, node_uuid, logged_user["id"], user_project["uuid"], rabbit_channels)
    def predicate2() -> bool:
        return mock_log_handler_fct.call_count == (NUMBER_OF_MESSAGES+1) and \
            mock_node_update_handler_fct.call_count == (NUMBER_OF_MESSAGES+1)
    await _wait_until(predicate, TIMEOUT_S)
    log_messages.append(final_log_message)
    log_calls = [call(json.dumps(message)) for message in log_messages]
    mock_log_handler_fct.assert_has_calls(log_calls, any_order=True)
    mock_node_update_handler_fct.assert_called()
    assert mock_node_update_handler_fct.call_count == (NUMBER_OF_MESSAGES+1)
