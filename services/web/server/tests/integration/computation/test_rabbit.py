# pylint:disable=wildcard-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import sys
from asyncio import Future
from pathlib import Path
from uuid import uuid4

import aio_pika
import pytest
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from simcore_sdk.config.rabbit import eval_broker
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.computation_config import CONFIG_SECTION_NAME

API_VERSION = "v0"

# Selection of core and tool services started in this swarm fixture (integration)
core_services = [
    'rabbit'
]

tool_services = [
    'flower'
]

@pytest.fixture(scope='session')
def here() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture
def webserver_service(loop, aiohttp_unused_port, aiohttp_server, app_config, rabbit_service):
    port = app_config["main"]["port"] = aiohttp_unused_port()
    host = app_config['main']['host'] = '127.0.0.1'

    assert app_config["rest"]["version"] == API_VERSION
    assert API_VERSION in app_config["rest"]["location"]

    app_config['storage']['enabled'] = False

    app_config["db"]["init_tables"] = True # inits postgres_service

    # fake config
    app = web.Application()
    app[APP_CONFIG_KEY] = app_config

    setup_computation(app, disable_login=True)

    server = loop.run_until_complete(aiohttp_server(app, port=port))
    yield server
    # cleanup


@pytest.fixture
def client(loop, webserver_service, aiohttp_client):
    client = loop.run_until_complete(aiohttp_client(webserver_service))
    return client

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

@pytest.fixture
async def log_channel(loop, rabbit_config, pika_connection):
    channel = await pika_connection.channel()
    pika_log_channel = rabbit_config["channels"]["log"]
    logs_exchange = await channel.declare_exchange(
        pika_log_channel, aio_pika.ExchangeType.FANOUT,
        auto_delete=True
    )
    yield logs_exchange

@pytest.fixture
async def progress_channel(loop, rabbit_config, pika_connection):
    channel = await pika_connection.channel()
    pika_progress_channel = rabbit_config["channels"]["log"]
    progress_exchange = await channel.declare_exchange(
        pika_progress_channel, aio_pika.ExchangeType.FANOUT,
        auto_delete=True
    )
    yield progress_exchange

@pytest.fixture(scope="session")
def node_uuid() -> str:
    return str(uuid4())

@pytest.fixture(scope="session")
def fake_log_message(node_uuid: str):
    yield {
        "Channel":"Log",
        "Messages": ["Some fake message"],
        "Node": node_uuid
    }

@pytest.fixture(scope="session")
def fake_progress_message(node_uuid: str):
    yield {
        "Channel":"Progress",
        "Progress": 0.56,
        "Node": node_uuid
    }

# ------------------------------------------
async def test_rabbit_log_connection(loop, client, log_channel, fake_log_message, mocker):
    mock = mocker.patch('simcore_service_webserver.computation_subscribe.sio.emit', return_value=Future())
    mock.return_value.set_result("")

    for i in range(1000):
        await log_channel.publish(
            aio_pika.Message(
                body=json.dumps(fake_log_message).encode(),
                content_type="text/json"), routing_key = ""
            )


    mock.assert_called_with("logger", data=json.dumps(fake_log_message))

async def test_rabbit_progress_connection(loop, client, progress_channel, fake_progress_message, mocker):
    mock = mocker.patch('simcore_service_webserver.computation_subscribe.sio.emit', return_value=Future())
    mock.return_value.set_result("")

    for i in range(1000):
        await progress_channel.publish(
            aio_pika.Message(
                body=json.dumps(fake_progress_message).encode(),
                content_type="text/json"), routing_key = ""
            )


    mock.assert_called_with("progress", data=json.dumps(fake_progress_message))
