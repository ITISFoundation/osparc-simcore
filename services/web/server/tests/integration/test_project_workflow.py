"""
    TODO: move to system testing: shall test different workflows on framework studies (=project)
        e.g. run, pull, push ,... pipelines
        This one here is too similar to unit/with_postgres/test_projects.py
"""

# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import sys
from copy import deepcopy
from pathlib import Path
from pprint import pprint
from typing import Dict, List

import pytest
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.projects.projects_handlers import Fake
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from utils_assert import assert_status
from utils_login import LoggedUser

API_VERSION = "v0"

# Selection of core and tool services started in this swarm fixture (integration)
core_services = [
    'apihub',
    'postgres'
]

tool_services = [
#    'adminer'
]

@pytest.fixture(scope='session')
def here() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

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
def fake_project(fake_data_dir: Path) -> Dict:
    with (fake_data_dir / "fake-project.json").open() as fp:
        yield json.load(fp)

@pytest.fixture
def webserver_service(loop, docker_stack, aiohttp_server, aiohttp_unused_port, api_specs_dir, app_config):
    port = app_config["main"]["port"] = aiohttp_unused_port()
    app_config['main']['host'] = '127.0.0.1'

    assert app_config["rest"]["version"] == API_VERSION
    assert API_VERSION in app_config["rest"]["location"]

    app_config['storage']['enabled'] = False
    app_config['rabbit']['enabled'] = False

    app = web.Application()
    app[APP_CONFIG_KEY] = app_config
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app, debug=True)
    setup_login(app)
    assert setup_projects(app)

    yield loop.run_until_complete( aiohttp_server(app, port=port) )

@pytest.fixture
def client(loop, webserver_service, aiohttp_client):
    client = loop.run_until_complete(aiohttp_client(webserver_service))
    yield client

@pytest.fixture
async def logged_user(client): #, role: UserRole):
    """ adds a user in db and logs in with client

    NOTE: role fixture is defined as a parametrization below
    """
    role = UserRole.USER # TODO: parameterize roles

    async with LoggedUser(
        client,
        {"role": role.name},
        check_if_succeeds = role!=UserRole.ANONYMOUS
    ) as user:
        yield user

# Tests CRUD operations --------------------------------------------
# TODO: merge both unit/with_postgress/test_projects

async def _request_list(client) -> List[Dict]:
    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(start=0, count=3))

    projects, _ = await assert_status(resp, web.HTTPOk)

    return projects

async def _request_get(client, pid) -> Dict:
    url = client.app.router["get_project"].url_for(project_id=pid)
    resp = await client.get(url)

    project, _ = await assert_status(resp, web.HTTPOk)

    return project

async def _request_create(client, project):
    url = client.app.router["create_projects"].url_for()
    resp = await client.post(url, json=project)

    new_project, _ = await assert_status(resp, web.HTTPCreated)

    return new_project

async def _request_update(client, project, pid):
    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(project_id=pid)
    resp = await client.put(url, json=project)

    updated_project, _ = await assert_status(resp, web.HTTPOk)

    return updated_project

async def _request_delete(client, pid):
    url = client.app.router["delete_project"].url_for(project_id=pid)
    resp = await client.delete(url)

    await assert_status(resp, web.HTTPNoContent)



async def test_workflow(client, fake_project, logged_user):
    # empty list
    projects = await _request_list(client)
    assert not projects

    # creation
    await _request_create(client, fake_project)

    # list not empty
    projects = await _request_list(client)
    assert len(projects) == 1
    assert projects[0] == fake_project

    modified_project = deepcopy(projects[0])
    modified_project["name"] = "some other name"
    modified_project["description"] = "John Raynor killed Kerrigan"
    modified_project["workbench"]["ReNamed"] =  modified_project["workbench"].pop("Xw)F")
    modified_project["workbench"]["ReNamed"]["position"]["x"] = 0
    # modify
    pid = modified_project["uuid"]
    await _request_update(client, modified_project, pid)

    # list not empty
    projects = await _request_list(client)
    assert len(projects) == 1
    assert projects[0] == modified_project

    # get
    project = await _request_get(client, pid)
    assert project == modified_project

    # delete
    await _request_delete(client, pid)

    # list empty
    projects = await _request_list(client)
    assert not projects


async def test_get_invalid_project(client, logged_user):
    url = client.app.router["get_project"].url_for(project_id="some-fake-id")
    resp = await client.get(url)

    await assert_status(resp, web.HTTPNotFound)


async def test_update_invalid_project(client, logged_user):
    url = client.app.router["replace_project"].url_for(project_id="some-fake-id")
    resp = await client.get(url)

    await assert_status(resp, web.HTTPNotFound)


async def test_delete_invalid_project(client, logged_user):
    url = client.app.router["delete_project"].url_for(project_id="some-fake-id")
    resp = await client.delete(url)

    await assert_status(resp, web.HTTPNotFound)


async def test_list_template_projects(client, logged_user, fake_db,
    fake_template_projects,
    fake_template_projects_isan,
    fake_template_projects_osparc
):
    fake_db.load_template_projects()
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(type="template"))

    projects, _ = await assert_status(resp, web.HTTPOk)

    # fake-template-projects.json + fake-template-projects.isan.json + fake-template-projects.osparc.json
    assert len(projects) == (len(fake_template_projects) + \
                                len(fake_template_projects_isan) + \
                                len(fake_template_projects_osparc))


async def test_project_uuid_uniqueness(client, logged_user, fake_project):
    # create the project once
    await _request_create(client, fake_project)
    # create a second project with same uuid shall fail
    with pytest.raises(AssertionError):
        await _request_create(client, fake_project)
    # delete
    pid = fake_project["uuid"]
    await _request_delete(client, pid)
