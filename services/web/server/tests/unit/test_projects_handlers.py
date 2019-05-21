# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import collections
import json
from asyncio import Future
from copy import deepcopy
from pathlib import Path
from typing import Dict

import pytest
from aiohttp import web
from yarl import URL

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.projects.projects_handlers import Fake
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.session import setup_session

import aiohttp_security.api
from simcore_service_webserver.security import setup_security

API_VERSION = "v0"
RESOURCE_NAME = 'projects'
FAKE_USER_ID = -1 # For testing purposes


@pytest.fixture(scope="session")
def fake_template_projects(package_dir: Path) -> Dict:
    projects_file = package_dir / "data" / "fake-template-projects.json"
    assert projects_file.exists()
    with projects_file.open() as fp:
        return json.load(fp)

@pytest.fixture(scope="session")
def fake_template_projects_isan(package_dir: Path) -> Dict:
    projects_file = package_dir / "data" / "fake-template-projects.isan.json"
    assert projects_file.exists()
    with projects_file.open() as fp:
        return json.load(fp)

@pytest.fixture(scope="session")
def fake_template_projects_osparc(package_dir: Path) -> Dict:
    projects_file = package_dir / "data" / "fake-template-projects.osparc.json"
    assert projects_file.exists()
    with projects_file.open() as fp:
        return json.load(fp)

@pytest.fixture
def fake_db():
    Fake.reset()
    yield Fake
    Fake.reset()

@pytest.fixture
def disable_permission_checks(mocker):
    mock1 = mocker.patch.object(aiohttp_security.api, "authorized_userid", return_value=Future(), autospec=True)
    mock1.return_value.set_result(FAKE_USER_ID)

    mock2 = mocker.patch.object(aiohttp_security.api, "permits", return_value=Future(), autospec=True)
    mock2.return_value.set_result(True)
    yield mock1, mock2

@pytest.fixture
def client(loop, aiohttp_client, aiohttp_unused_port, api_specs_dir, fake_db, disable_permission_checks):
    app = web.Application()

    server_kwargs={'port': aiohttp_unused_port(), 'host': 'localhost'}
    # fake config
    app[APP_CONFIG_KEY] = {
        "main": server_kwargs,
        "rest": {
            "version": "v0",
            "location": str(api_specs_dir / API_VERSION / "openapi.yaml")
        },
        "db": {"enabled": False}, # inits postgres_service,
        "projects": {
            "location": str(api_specs_dir / API_VERSION / "components/schemas/project-v0.0.1.json")
        }
    }

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app, debug=True)
    setup_projects(app,
        enable_fake_data=False, # no fake data
        disable_login=True # TODO: Move this out and use mocks instead
    )

    yield loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )


# Tests CRUD operations --------------------------------------------
PREFIX = "/" + API_VERSION


# TODO: template for CRUD testing?
# TODO: create parametrize fixture with resource_name


async def test_create(client, fake_project, mocker):
    pid = fake_project["uuid"]
    #--------------------------

    url = client.app.router["create_projects"].url_for()
    assert str(url) == PREFIX + "/%s" % RESOURCE_NAME

    # POST /v0/projects
    mock = mocker.patch('simcore_service_webserver.projects.projects_handlers.ProjectDB.add_projects', return_value=Future())
    mock.return_value.set_result("")

    resp = await client.post(url, json=fake_project)
    text = await resp.text()

    payload = await resp.json()
    assert resp.status == 201, payload
    project, error = unwrap_envelope(payload)

    assert not error

    mock.assert_called_once_with([fake_project], -1, db_engine=None)

async def test_list(client, mocker, fake_project):
    mock = mocker.patch('simcore_service_webserver.projects.projects_handlers.ProjectDB.load_user_projects', return_value=Future())
    mock.return_value.set_result([fake_project])

    # list all user projects
    url = client.app.router["list_projects"].url_for()
    assert str(url) == PREFIX + "/%s" % RESOURCE_NAME

    # GET /v0/projects
    resp = await client.get(url.with_query(start=1, count=2))
    payload = await resp.json()
    assert resp.status == 200, payload

    projects, error = unwrap_envelope(payload)
    assert not error
    assert not projects
    mock.assert_called_once_with(user_id=FAKE_USER_ID, db_engine=None)

    resp = await client.get(url.with_query(start=0, count=0))
    payload = await resp.json()
    assert resp.status == 200, payload

    projects, error = unwrap_envelope(payload)
    assert not error
    assert not projects
    mock.assert_called_with(user_id=FAKE_USER_ID, db_engine=None)

    resp = await client.get(url.with_query(start=0, count=2))
    payload = await resp.json()
    assert resp.status == 200, payload

    projects, error = unwrap_envelope(payload)
    assert not error
    assert projects
    mock.assert_called_with(user_id=FAKE_USER_ID, db_engine=None)

    assert len(projects)==1
    assert projects[0] == fake_project

async def test_list_template_projects(client, fake_db, mocker, fake_project: Dict, fake_template_projects: Dict, fake_template_projects_isan: Dict, fake_template_projects_osparc: Dict):
    fake_db.load_template_projects()

    url = client.app.router["list_projects"].url_for()
    assert str(url) == PREFIX + "/%s" % RESOURCE_NAME
    # list all template projects
    mock = mocker.patch('simcore_service_webserver.projects.projects_handlers.ProjectDB.load_template_projects', return_value=Future())
    mock.return_value.set_result([fake_project])
    resp = await client.get(url.with_query(type="template"))
    payload = await resp.json()
    assert resp.status == 200, payload

    projects, error = unwrap_envelope(payload)
    assert not error
    mock.assert_called_with(db_engine=None)
    # fake-template-projects.json + fake-template-projects.isan.json + fake-template-projects.osparc.json + fake project

    assert len(projects) == (len(fake_template_projects) + len(fake_template_projects_isan) + len(fake_template_projects_osparc) + 1)

async def test_get(client, fake_project, mocker):
    pid = fake_project["uuid"]
    #-----------------
    mock = mocker.patch('simcore_service_webserver.projects.projects_handlers.ProjectDB.get_user_project', return_value=Future())
    mock.return_value.set_result(fake_project)
    # get one
    url = client.app.router["get_project"].url_for(project_id=pid)
    assert str(url) == PREFIX + "/%s/%s" % (RESOURCE_NAME, pid)

    # GET /v0/projects/{project_id}
    resp = await client.get(url)
    payload = await resp.json()
    assert resp.status == 200, payload

    mock.assert_called_once_with(FAKE_USER_ID, pid, db_engine=None)

    project, error = unwrap_envelope(payload)
    assert not error
    assert project

    assert project == fake_project

async def test_get_project_template(client, fake_db, fake_template_projects: Dict, fake_template_projects_isan: Dict, fake_template_projects_osparc: Dict):
    fake_db.load_template_projects()
    template_projects = fake_template_projects
    template_projects.extend(fake_template_projects_isan)
    template_projects.extend(fake_template_projects_osparc)

    for template in template_projects:
        pid = template["uuid"]
        url = client.app.router["get_project"].url_for(project_id=pid)
        assert str(url) == PREFIX + "/%s/%s" % (RESOURCE_NAME, pid)

        # GET /v0/projects/{project_id}
        resp = await client.get(url)
        payload = await resp.json()
        assert resp.status == 200, payload

        project, error = unwrap_envelope(payload)
        assert not error
        assert project

        assert project == template

async def test_update(client, fake_db, fake_project, mocker):
    pid = fake_project["uuid"]
    #-----------------
    #
    # In a PUT request, the enclosed entity is considered to be a modified version of
    # the resource stored on the origin server, and the client is requesting that the
    # stored version be replaced.
    #
    # With PATCH, however, the enclosed entity contains a set of instructions describing how a
    # resource currently residing on the origin server should be modified to produce a new version.
    #
    # Also, another difference is that when you want to update a resource with PUT request, you have to send
    # the full payload as the request whereas with PATCH, you only send the parameters which you want to update.
    #
    mock = mocker.patch('simcore_service_webserver.projects.projects_handlers.ProjectDB.update_user_project', return_value=Future())
    mock.return_value.set_result(None)

    url = client.app.router["replace_project"].url_for(project_id=pid)
    assert str(url) == PREFIX + "/%s/%s" % (RESOURCE_NAME, pid)

    # PUT /v0/projects/{project_id}
    resp = await client.put(url, json=fake_project)
    payload = await resp.json()
    assert resp.status == 200, payload

    project, error = unwrap_envelope(payload)
    assert not error
    assert not project

    mock.assert_called_once_with(fake_project, FAKE_USER_ID, pid, db_engine=None)

async def test_delete(client, fake_db, fake_project, mocker):
    pid = fake_project["uuid"]
    # -------------
    mock = mocker.patch('simcore_service_webserver.projects.projects_handlers.ProjectDB.delete_user_project', return_value=Future())
    mock.return_value.set_result(None)

    url = client.app.router["delete_project"].url_for(project_id=pid)
    assert str(url) == PREFIX + "/%s/%s" % (RESOURCE_NAME, pid)

    # DELETE /v0/projects/{project_id}
    resp = await client.delete(url)
    payload = await resp.json()

    assert resp.status == 204, payload

    data, error = unwrap_envelope(payload)
    assert not data
    assert not error

    mock.assert_called_once_with(FAKE_USER_ID, pid, db_engine=None)
