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
from typing import Dict

import pytest
import yaml
from aiohttp import web
from yarl import URL

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import unwrap_envelope
from simcore_sdk.models.pipeline_models import (
    SUCCESS, ComputationalPipeline, ComputationalTask)
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.users import setup_users
from utils_assert import assert_status
from utils_login import LoggedUser
from utils_projects import NewProject

API_VERSION = "v0"
API_PREFIX = "/" + API_VERSION

# TODO: create conftest at computation/ folder level

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
#    'adminer',
#    'flower',
#    'portainer'
]

@pytest.fixture(scope='session')
def here() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client, app_config, here, docker_compose_file):
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
    setup_session(app)
    setup_security(app)
    setup_rest(app, debug=True)
    setup_login(app)
    setup_projects(app)
    setup_computation(app)

    yield loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': port,
        'host': 'localhost'
    }))

    # cleanup
    final_config_path.unlink()


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

@pytest.fixture
def mock_project(fake_data_dir, mock_workbench_payload):
    with (fake_data_dir / "fake-project.json").open() as fp:
        project = json.load(fp)
    project["workbench"] = mock_workbench_payload["workbench"]
    return project


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
async def user_project(client, mock_project, logged_user):
    mock_project["prjOwner"] = logged_user["name"]

    async with NewProject(
        mock_project,
        client.app,
        user_id=logged_user["id"]
    ) as project:
        yield project

# HELPERS ----------------------------------
def assert_db_contents(project_id, postgres_session,
        mock_workbench_payload, mock_workbench_adjacency_list,
        check_outputs:bool
    ):
    pipeline_db = postgres_session.query(ComputationalPipeline)\
        .filter(ComputationalPipeline.project_id == project_id).one()
    assert pipeline_db.project_id == project_id
    assert pipeline_db.dag_adjacency_list == mock_workbench_adjacency_list

    # check db comp_tasks
    tasks_db = postgres_session.query(ComputationalTask)\
        .filter(ComputationalTask.project_id == project_id).all()
    mock_pipeline = mock_workbench_payload
    assert len(tasks_db) == len(mock_pipeline)

    for task_db in tasks_db:
        # assert task_db.task_id == (i+1)
        assert task_db.project_id == project_id
        assert task_db.node_id in mock_pipeline.keys()

        assert task_db.inputs == mock_pipeline[task_db.node_id].get("inputs")

        if check_outputs:
            assert task_db.outputs == mock_pipeline[task_db.node_id].get("outputs")

        assert task_db.image["name"] == mock_pipeline[task_db.node_id]["key"]
        assert task_db.image["tag"] == mock_pipeline[task_db.node_id]["version"]

def assert_sleeper_services_completed(project_id, postgres_session):
    # we wait 15 secs before testing...
    time.sleep(15)
    pipeline_db = postgres_session.query(ComputationalPipeline)\
        .filter(ComputationalPipeline.project_id == project_id).one()
    tasks_db = postgres_session.query(ComputationalTask)\
        .filter(ComputationalTask.project_id == project_id).all()
    for task_db in tasks_db:
        if "sleeper" in task_db.image["name"]:
            assert task_db.state == SUCCESS


# TESTS ------------------------------------------
async def test_check_health(docker_stack, client):
    # TODO: check health of all core_services in list above!
    resp = await client.get( API_VERSION + "/")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data['name'] == 'simcore_service_webserver'
    assert data['status'] == 'SERVICE_RUNNING'


@pytest.mark.parametrize("user_role,expected_response", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_start_pipeline(client, postgres_session, celery_service, sleeper_service,
        logged_user, user_project,
        mock_workbench_adjacency_list,
        expected_response
    ):
    project_id = user_project["uuid"]
    mock_workbench_payload = user_project['workbench']

    url = client.app.router["start_pipeline"].url_for(project_id=project_id)
    assert url == URL(API_PREFIX + "/computation/pipeline/{}/start".format(project_id))

    # POST /v0/computation/pipeline/{project_id}/start
    resp = await client.post(url)
    data, error = await assert_status(resp, expected_response)

    if not error:
        assert "pipeline_name" in data
        assert "project_id" in data
        assert data['project_id'] == project_id

        assert_db_contents(project_id, postgres_session, mock_workbench_payload,
            mock_workbench_adjacency_list, check_outputs=False)
        # assert_sleeper_services_completed(project_id, postgres_session)


@pytest.mark.parametrize("user_role,expected_response", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPNoContent),
    (UserRole.USER, web.HTTPNoContent),
    (UserRole.TESTER, web.HTTPNoContent),
])
async def test_update_pipeline(client, docker_stack, postgres_session,
        logged_user, user_project,
        mock_workbench_payload, mock_workbench_adjacency_list,
        expected_response
    ):
    project_id = user_project["uuid"]
    assert user_project['workbench'] == mock_workbench_payload['workbench']

    url = client.app.router["update_pipeline"].url_for(project_id=project_id)
    assert url == URL(API_PREFIX + "/computation/pipeline/{}".format(project_id))

    # POST /v0/computation/pipeline/{project_id}
    resp = await client.put(url)

    data, error = await assert_status(resp, expected_response)

    if not error:
        # check db comp_pipeline
        assert_db_contents(project_id, postgres_session, mock_workbench_payload['workbench'],
            mock_workbench_adjacency_list, check_outputs=True)
