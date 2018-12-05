# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import uuid
from pathlib import Path
import yaml

import pytest
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.users import setup_users

API_VERSION = "v0"

@pytest.fixture
def webserver_service(loop, aiohttp_unused_port, aiohttp_server, app_config, here, docker_compose_file):
    port = app_config["main"]["port"] = aiohttp_unused_port()
    host = app_config['main']['host'] = '127.0.0.1'

    assert app_config["rest"]["version"] == API_VERSION
    assert API_VERSION in app_config["rest"]["location"]

    app_config['storage']['enabled'] = False

    app_config["db"]["init_tables"] = True # inits postgres_service

    # TODO: parse_and_validate
    with (here / "config.app.yaml").open('wt') as f:
        yaml.dump(app_config, f, default_flow_style=False)

    # fake config
    app = web.Application()
    app[APP_CONFIG_KEY] = app_config

    setup_db(app)
    setup_rest(app, debug=True)
    setup_computation(app, disable_login=True)

    server = loop.run_until_complete(aiohttp_server(app, port=port))
    return server


@pytest.fixture
def client(loop, webserver_service, aiohttp_client):
    client = loop.run_until_complete(aiohttp_client(webserver_service))
    return client

@pytest.fixture
def project_id() -> str:
    return str(uuid.uuid4())

@pytest.fixture
def mock_workbench_payload(here):
    file_path = here / "workbench_payload.json"
    with file_path.open() as fp:
        return json.load(fp)
# ------------------------------------------

async def test_check_health(client):
    resp = await client.get("/v0/")
    payload = await resp.json()

    assert resp.status == 200, str(payload)
    data, error = tuple(payload.get(k) for k in ('data', 'error'))

    assert data
    assert not error

    assert data['name'] == 'simcore_service_webserver'
    assert data['status'] == 'SERVICE_RUNNING'

async def test_start_pipeline(client, project_id:str, mock_workbench_payload):
    import pdb; pdb.set_trace()
    resp = await client.post("/v0/computation/pipeline/{}/start".format(project_id),
        json = mock_workbench_payload,
    )
    payload = await resp.json()

    assert resp.status == 200, str(payload)
    data, error = tuple(payload.get(k) for k in ('data', 'error'))

    assert data
    assert not error

    assert "pipeline_name" in data
    assert "pipeline_id" in data
    # assert data['pipeline_name'] == 'simcore_service_webserver'
    assert data['pipeline_id'] == project_id
