# UNDER DEVELOPMENT

#
# - tests webserver/director and webserver/computation subsystems
#
# Implementing https://github.com/ITISFoundation/osparc-simcore/issues/784

# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from pathlib import Path
from typing import Dict

import jsonschema
import pytest
from aiohttp import web
from yarl import URL

from simcore_service_webserver.application import create_application
from utils_assert import assert_status

API_VERSION = "v0"
API_PREFIX = "/" + API_VERSION

# TODO: create conftest at computation/ folder level

# Selection of core and tool services started in this swarm fixture (integration)
core_services = [
    'director',
    'apihub',
    'postgres'
]

ops_services = [
    'minio'
#    'adminer',
#    'portainer'
]


@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client, app_config):
    port = app_config["main"]["port"] = aiohttp_unused_port()
    host = app_config['main']['host'] = '127.0.0.1'

    assert app_config["rest"]["version"] == API_VERSION
    assert API_VERSION in app_config["rest"]["location"]

    # disable unnecesary subsystems
    for subsystem in ('storage', ): # TODO: add here more!
        app_config[subsystem]['enabled'] = False

    import pdb; pdb.set_trace()
    app = create_application(app_config)

    # server and client
    yield loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': port,
        'host': host
    }))

    # teardown here ...


def test_it(client):
    import pdb; pdb.set_trace()


    pass


# 1 user, opens 1 project with N notebooks
#   user closes project
#

@pytest.fixture
def service_metadata_schema(osparc_simcore_root_dir: Path) -> Dict:
    jsonpath = osparc_simcore_root_dir / 'api/specs/shared/schemas/node-meta-v0.0.1.json'
    schema = json.load(jsonpath.read_text())
    return schema

async def test_service_api_workflow(client, jupyter_service, sleeper_service, service_metadata_schema):
    import pdb; pdb.set_trace()

    # List services in registry
    resp = await client.get(f"{API_PREFIX}/services?service_type=interactive")

    data, _ = await assert_status(resp, expected=web.HTTPOk)

    assert len(data) == 1

    import pdb; pdb.set_trace()
    jsonschema.validate(data[0], service_metadata_schema)

    # TODO: validation
    service_key, service_version = jupyter_service.split(":")

    srv = data[0]
    assert srv['key']==service_key
    assert srv['version']==service_version

    # Start backend dynamic service
    service_uuid = "dbf4ca52-266c-4a51-b020-708609a8a8f0"
    resp = await client.post( URL(f"{API_PREFIX}/running_interactive_services").with_query(
         service_key=service_key,
         service_version =service_version,
         service_uuid = service_uuid)
    )
    data, _ = await assert_status(resp, expected=web.HTTPCreated)

    service_basepath = data['service_basepath']
    # assert service_basepath == PROXY_MOUNTPOINT + "/" + service_uuid

   # Wait until service is responsive
    MAX_RESPONSE_TIME_SECS = 5

    resp = await client.get(f"{API_PREFIX}/running_interactive_services/{service_uuid}")
    data, _ = await assert_status(resp, expected=web.HTTPOk)




    # Talk with backend dynamic service ---------------------------------------------







def test_monitor_user_services(jupyter_service):
    # what resources
    # what if hits maximum?
    pass


# auto-stop ----

def test_policy_if_user_leaves():
    # What to do with user services...
    # when user disconnects/logout + timeout
    pass


def test_policy_if_project_finishes():
    # What to do with user services...
    # when user moves to dashboard, closes/deletes project + timeout
    pass
