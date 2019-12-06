# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import sys
from asyncio import gather, Task, sleep
from pathlib import Path
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
from simcore_service_webserver.resource_manager import setup_resource_manager
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio import setup_sockets
from utils_login import LoggedUser

API_VERSION = "v0"

# Selection of core and tool services started in this swarm fixture (integration)
core_services = [
    'apihub',
    'postgres',
    'redis',
    'rabbit'
]

ops_services = [
]

@pytest.fixture(scope='session')
def here() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture
def client(loop, aiohttp_client,
        app_config,    ## waits until swarm with *_services are up
        rabbit_service ## waits until rabbit is responsive
    ):
    assert app_config["rest"]["version"] == API_VERSION
    assert API_VERSION in app_config["rest"]["location"]

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
    setup_computation(app)
    setup_sockets(app)
    setup_resource_manager(app)

    yield loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': app_config["main"]["port"],
        'host': app_config['main']['host']
    }))

@pytest.fixture
async def logged_user(client, user_role: UserRole):
    """ adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds = user_role!=UserRole.ANONYMOUS
    ) as user:
        yield user

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

@pytest.fixture(scope="session")
def node_uuid() -> str:
    return str(uuid4())

@pytest.fixture(scope="session")
def user_id() -> str:
    return "some_id"

@pytest.fixture(scope="session")
def project_id() -> str:
    return "some_project_id"

# ------------------------------------------

@pytest.fixture(params=["log", "progress"])
async def all_in_one(request, loop, rabbit_config, pika_connection, node_uuid, user_id, project_id):
    # create rabbit pika exchange channel
    channel = await pika_connection.channel()
    pika_channel = rabbit_config["channels"][request.param]
    pika_exchange = await channel.declare_exchange(
        pika_channel, aio_pika.ExchangeType.FANOUT,
        auto_delete=True
    )

    # create corresponding message
    message = {
        "Channel":request.param.title(),
        "Progress": 0.56,
        "Node": node_uuid,
        "user_id": user_id,
        "project_id": project_id
    }

    # socket event
    socket_event_name = "logger" if request.param is "log" else "progress"
    yield {"rabbit_channel": pika_exchange, "data": message, "socket_name": socket_event_name}

@pytest.fixture
def tab_id():
    return str(uuid4())

@pytest.mark.parametrize("user_role", [
    (UserRole.GUEST),
    (UserRole.USER),
    (UserRole.TESTER),
])
async def test_rabbit_websocket_connection(logged_user,
                                            socketio_client, mocker,
                                            all_in_one, tab_id):
    rabbit_channel = all_in_one["rabbit_channel"]
    channel_message = all_in_one["data"]
    socket_event_name = all_in_one["socket_name"]

    sio = await socketio_client(tab_id)
    # register mock function
    log_fct = mocker.Mock()
    sio.on(socket_event_name, handler=log_fct)
    NUMBER_OF_MESSAGES = 500
    WAIT_FOR_MESSAGES_S = 5
    # the user id is not the one from the logged user, there should be no call to the function
    publish_tasks = [rabbit_channel.publish(
            aio_pika.Message(
                body=json.dumps(channel_message).encode(),
                content_type="text/json"), routing_key = ""
            ) for i in range(NUMBER_OF_MESSAGES)]
    await gather(*publish_tasks, return_exceptions=True)
    await sleep(WAIT_FOR_MESSAGES_S)
    log_fct.assert_not_called()

    # let's set the correct user id
    channel_message["user_id"] = logged_user["id"]
    publish_tasks = [rabbit_channel.publish(
            aio_pika.Message(
                body=json.dumps(channel_message).encode(),
                content_type="text/json"), routing_key = ""
            ) for i in range(NUMBER_OF_MESSAGES)]
    await gather(*publish_tasks, return_exceptions=True)
    await sleep(WAIT_FOR_MESSAGES_S)

    log_fct.assert_called()
    calls = [call(json.dumps(channel_message))]
    log_fct.assert_has_calls(calls)
