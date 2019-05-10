# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from pprint import pprint

import pytest
import yaml
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import unwrap_envelope
from simcore_sdk.models.pipeline_models import (
    SUCCESS, ComputationalPipeline, ComputationalTask)
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.users import setup_users

API_VERSION = "v0"

# Selection of core and tool services started in this swarm fixture (integration)
core_services = [
    'director',
    'apihub',
    'rabbit',
    'postgres',
    'sidecar',
    'storage',
    'minio'
]

tool_services = [
    'adminer',
    'flower',
    'portainer'
]

@pytest.fixture(scope='session')
def here() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture
def webserver_service(loop, aiohttp_unused_port, aiohttp_server, app_config, here, docker_compose_file):
    port = app_config["main"]["port"] = aiohttp_unused_port()
    host = app_config['main']['host'] = '127.0.0.1'

    assert app_config["rest"]["version"] == API_VERSION
    assert API_VERSION in app_config["rest"]["location"]

    app_config['storage']['enabled'] = False
    app_config["db"]["init_tables"] = True # inits postgres_service

    final_config_path = here / "config.app.yaml"
    with final_config_path.open('wt') as f:
        yaml.dump(app_config, f, default_flow_style=False)

    # fake config
    app = web.Application()
    app[APP_CONFIG_KEY] = app_config

    pprint(app_config)

    setup_db(app)
    setup_rest(app, debug=True)
    setup_computation(app, disable_login=True)

    server = loop.run_until_complete(aiohttp_server(app, port=port))

    yield server

    # cleanup
    final_config_path.unlink()


@pytest.fixture
def client(loop, webserver_service, aiohttp_client):
    client = loop.run_until_complete(aiohttp_client(webserver_service))
    return client

@pytest.fixture
def project_id() -> str:
    return str(uuid.uuid4())

@pytest.fixture
def mock_workbench_payload(here):
    file_path = here / "workbench_sleeper_payload.json"
    with file_path.open() as fp:
        return json.load(fp)

@pytest.fixture
def mock_workbench_adjacency_list(here):
    file_path = here / "workbench_sleeper_dag_adjacency_list.json"
    with file_path.open() as fp:
        return json.load(fp)
# ------------------------------------------

async def test_check_health(docker_stack, client):
    resp = await client.get("/%s/" % API_VERSION)
    payload = await resp.json()

    assert resp.status == 200, str(payload)
    data, error = unwrap_envelope(payload)

    assert data
    assert not error

    assert data['name'] == 'simcore_service_webserver'
    assert data['status'] == 'SERVICE_RUNNING'

def _check_db_contents(project_id, postgres_session, mock_workbench_payload, mock_workbench_adjacency_list, check_outputs:bool):
    pipeline_db = postgres_session.query(ComputationalPipeline).filter(ComputationalPipeline.project_id == project_id).one()
    assert pipeline_db.project_id == project_id
    assert pipeline_db.dag_adjacency_list == mock_workbench_adjacency_list

    # check db comp_tasks
    tasks_db = postgres_session.query(ComputationalTask).filter(ComputationalTask.project_id == project_id).all()
    mock_pipeline = mock_workbench_payload["workbench"]
    assert len(tasks_db) == len(mock_pipeline)
    for i in range(len(tasks_db)):
        task_db = tasks_db[i]
        # assert task_db.task_id == (i+1)
        assert task_db.project_id == project_id
        assert task_db.node_id in mock_pipeline.keys()
        if "inputs" in mock_pipeline[task_db.node_id]:
            assert task_db.inputs == mock_pipeline[task_db.node_id]["inputs"]
        else:
            assert task_db.inputs == None
        if check_outputs:
            if "outputs" in mock_pipeline[task_db.node_id]:
                assert task_db.outputs == mock_pipeline[task_db.node_id]["outputs"]
            else:
                assert task_db.outputs == None
        assert task_db.image["name"] == mock_pipeline[task_db.node_id]["key"]
        assert task_db.image["tag"] == mock_pipeline[task_db.node_id]["version"]

def _check_sleeper_services_completed(project_id, postgres_session):
    # we wait 15 secs before testing...
    time.sleep(15)
    pipeline_db = postgres_session.query(ComputationalPipeline).filter(ComputationalPipeline.project_id == project_id).one()
    tasks_db = postgres_session.query(ComputationalTask).filter(ComputationalTask.project_id == project_id).all()
    for i in range(len(tasks_db)):
        task_db = tasks_db[i]
        if "sleeper" in task_db.image["name"]:
            assert task_db.state == SUCCESS

async def test_start_pipeline(sleeper_service, client, project_id:str, mock_workbench_payload, mock_workbench_adjacency_list, postgres_session, celery_service):

    resp = await client.post("/{}/computation/pipeline/{}/start".format(API_VERSION, project_id),
        json = mock_workbench_payload,
    )
    assert resp.status == 200, str(await resp.text())
    payload = await resp.json()
    data, error = unwrap_envelope(payload)

    assert data
    assert not error

    assert "pipeline_name" in data
    assert "project_id" in data
    assert data['project_id'] == project_id
    # check db comp_pipeline
    _check_db_contents(project_id, postgres_session, mock_workbench_payload, mock_workbench_adjacency_list, check_outputs=False)
    # _check_sleeper_services_completed(project_id, postgres_session)

async def test_update_pipeline(docker_stack, client, project_id:str, mock_workbench_payload, mock_workbench_adjacency_list, postgres_session):
    resp = await client.put("/{}/computation/pipeline/{}".format(API_VERSION, project_id),
        json = mock_workbench_payload,
    )
    assert resp.status == 204, str(await resp.text())
    payload = await resp.json()
    data, error = unwrap_envelope(payload)

    assert not data
    assert not error
    # check db comp_pipeline
    _check_db_contents(project_id, postgres_session, mock_workbench_payload, mock_workbench_adjacency_list, check_outputs=True)
