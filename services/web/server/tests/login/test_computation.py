# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import uuid
from pathlib import Path

import pytest
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.users import setup_users
from utils_login import LoggedUser

API_VERSION = "v0"

@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client, app_cfg, postgres_service):
    app = web.Application()
    port = app_cfg["main"]["port"] = aiohttp_unused_port()

    assert app_cfg["rest"]["version"] == API_VERSION
    assert API_VERSION in app_cfg["rest"]["location"]

    app_cfg["db"]["init_tables"] = True # inits postgres_service

    # fake config
    app[APP_CONFIG_KEY] = app_cfg

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app, debug=True)
    setup_login(app)
    setup_users(app)
    setup_computation(app)

    client = loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': port,
        'host': 'localhost'
    }))
    return client

@pytest.fixture
def project_id() -> str:
    return str(uuid.uuid4())

@pytest.fixture
def mock_workbench_payload(mock_dir):
    file_path = mock_dir / "workbench_payload.json"
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
    async with LoggedUser(client) as user:
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
