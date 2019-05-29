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
from simcore_service_webserver.session import setup_session
from utils_login import LoggedUser

API_VERSION = "v0"

# Tests CRUD operations --------------------------------------------
PREFIX = "/" + API_VERSION

# Selection of core and tool services started in this swarm fixture (integration)
core_services = [
    'apihub',
    'postgres'
]

tool_services = [
    'adminer'
]

@pytest.fixture(scope='session')
def here() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

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
    setup_projects(app,
        enable_fake_data=False, # no fake data
        disable_login=False
    )

    yield loop.run_until_complete( aiohttp_server(app, port=port) )

@pytest.fixture
def client(loop, webserver_service, aiohttp_client):
    client = loop.run_until_complete(aiohttp_client(webserver_service))
    yield client

@pytest.fixture
def fake_project(fake_data_dir: Path) -> Dict:
    with (fake_data_dir / "fake-project.json").open() as fp:
        yield json.load(fp)


async def _list_projects(client) -> List[Dict]:
    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(start=0, count=3))
    payload = await resp.json()
    assert resp.status == 200, payload

    projects, error = unwrap_envelope(payload)
    assert not error, pprint(error)

    return projects

async def _get_project(client, pid) -> Dict:
    url = client.app.router["get_project"].url_for(project_id=pid)
    resp = await client.get(url)
    payload = await resp.json()
    assert resp.status == 200, payload

    project, error = unwrap_envelope(payload)
    assert not error, pprint(error)
    assert project

    return project

async def _create_project(client, project):
    url = client.app.router["create_projects"].url_for()
    resp = await client.post(url, json=project)
    payload = await resp.json()
    assert resp.status == 201, payload
    project, error = unwrap_envelope(payload)
    assert project
    assert not error, pprint(error)

async def _update_project(client, project, pid):
    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(project_id=pid)
    resp = await client.put(url, json=project)
    payload = await resp.json()
    assert resp.status == 200, payload

    project, error = unwrap_envelope(payload)
    assert not error, pprint(error)
    assert not project

async def _delete_project(client, pid):
    url = client.app.router["delete_project"].url_for(project_id=pid)
    resp = await client.delete(url)
    payload = await resp.json()
    assert resp.status == 204, payload

    project, error = unwrap_envelope(payload)
    assert not error, pprint(error)
    assert not project

async def test_workflow(loop, client, fake_project):
    async with LoggedUser(client):
        # empty list
        projects = await _list_projects(client)
        assert not projects
        # creation
        await _create_project(client, fake_project)
        # list not empty
        projects = await _list_projects(client)
        assert len(projects) == 1
        assert projects[0] == fake_project

        modified_project = deepcopy(projects[0])
        modified_project["name"] = "some other name"
        modified_project["workbench"]["ReNamed"] =  modified_project["workbench"].pop("Xw)F")
        modified_project["workbench"]["ReNamed"]["position"]["x"] = 0
        # modifiy
        pid = modified_project["uuid"]
        await _update_project(client, modified_project, pid)

        # list not empty
        projects = await _list_projects(client)
        assert len(projects) == 1
        assert projects[0] == modified_project

        # get
        project = await _get_project(client, pid)
        assert project == modified_project

        # delete
        await _delete_project(client, pid)
        # list empty
        projects = await _list_projects(client)
        assert not projects

async def test_get_invalid_project(loop, client):
    async with LoggedUser(client):
        url = client.app.router["get_project"].url_for(project_id="some-fake-id")
        resp = await client.get(url)
        payload = await resp.json()

        assert resp.status == 404, payload
        data, error = unwrap_envelope(payload)
        assert not data
        assert error

async def test_update_invalid_project(loop, client):
    async with LoggedUser(client):
        url = client.app.router["replace_project"].url_for(project_id="some-fake-id")
        resp = await client.get(url)
        payload = await resp.json()

        assert resp.status == 404, payload
        data, error = unwrap_envelope(payload)
        assert not data
        assert error

async def test_delete_invalid_project(loop, client):
    async with LoggedUser(client):
        url = client.app.router["delete_project"].url_for(project_id="some-fake-id")
        resp = await client.delete(url)
        payload = await resp.json()

        assert resp.status == 404, pprint(payload)
        data, error = unwrap_envelope(payload)
        assert not data
        assert error

@pytest.fixture
def fake_db():
    Fake.reset()
    yield Fake
    Fake.reset()

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

async def test_list_template_projects(loop, client, fake_db, fake_template_projects, fake_template_projects_isan, fake_template_projects_osparc):
    fake_db.load_template_projects()
    async with LoggedUser(client):
        url = client.app.router["list_projects"].url_for()
        resp = await client.get(url.with_query(type="template"))
        payload = await resp.json()
        assert resp.status == 200, pprint(payload)

        projects, error = unwrap_envelope(payload)
        assert not error, pprint(error)
        # fake-template-projects.json + fake-template-projects.isan.json + fake-template-projects.osparc.json
        assert len(projects) == (len(fake_template_projects) + len(fake_template_projects_isan) + len(fake_template_projects_osparc))

async def test_project_uuid_uniqueness(loop, client, fake_project):
    async with LoggedUser(client):
        # create the project once
        await _create_project(client, fake_project)
        # create a second project with same uuid shall fail
        with pytest.raises(AssertionError):
            await _create_project(client, fake_project)
        # delete
        pid = fake_project["uuid"]
        await _delete_project(client, pid)
