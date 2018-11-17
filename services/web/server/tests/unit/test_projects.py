# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import collections

import pytest
from aiohttp import web
from yarl import URL

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.openapi_validation import validate_data
from servicelib.rest_responses import unwrap_envelope

from simcore_service_webserver.db import setup_db
from simcore_service_webserver.rest import APP_OPENAPI_SPECS_KEY, setup_rest
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.projects_handlers import Fake


API_VERSION = "v0"
RESOURCE_NAME = 'projects'


@pytest.fixture
def fake_db():
    Fake.reset()
    yield Fake
    Fake.reset()

@pytest.fixture
def client(loop, aiohttp_client, aiohttp_unused_port, api_specs_dir, fake_db):
    app = web.Application()

    server_kwargs={'port': aiohttp_unused_port(), 'host': 'localhost'}
    # fake config
    app[APP_CONFIG_KEY] = {
        "main": server_kwargs,
        "rest": {
            "version": "v0",
            "location": str(api_specs_dir / API_VERSION / "openapi.yaml")
        }
    }

    # setup_db(app)
    setup_session(app)
    setup_rest(app, debug=True)
    setup_projects(app, debug=True)

    yield loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )


@pytest
def fake_project():
    # TODO: create automatically fakes??
    #
    # generated from api/specs/webserver/v0/components/schemas/project-v0.0.1.json
    # using http://json-schema-faker.js.org/
    return {
        "projectUuid": "f298d06b-707a-6257-a462-d7bf73b76c0c",
        "name": "ex",
        "description": "anim sint pariatur do dolore",
        "notes": "enim nisi consequat",
        "owner": "dolore ad do consectetur",
        "collaborators": {
            "WS(q": [
            "write"
            ]
        },
        "creationDate": "1865-11-31T04:00:14Z",
        "lastChangeDate": "7364-11-30T10:4:52Z",
        "thumbnail": "sunt adipisicing enim anim nisi",
        "workbench": {
            "Xw)F": {
            "key": "service/dynamic/7r52.#`/`@jTV,fdk0[/J/<WB'/~+/f!<Y#M5/9751",
            "version": "0.2249944.0",
            "position": {
                "x": -29926723,
                "y": 92196123
            }
            }
        }
    }



# Tests CRUD operations --------------------------------------------
PREFIX = "/" + API_VERSION


# TODO: template for CRUD testing?
# TODO: create parametrize fixture with resource_name


async def test_create(client, fake_db, fake_project):

    url = client.app.router["create_projects"].url_for()
    assert url == PREFIX + "/%s" % RESOURCE_NAME
    resp = await client.post(url, json=fake_project)

    payload = await resp.json()
    assert resp.status == 201, payload
    project, error = unwrap_envelope(payload)
    # TODO:  there is no need to return data since everything is decided upon request

    assert not error

    assert fake_db.projects
    assert fake_db.projects[0] == fake_project


async def test_read_all(client, fake_db):
    fake_db.load_user_projects()
    fake_db.load_template_projects()

    # list all
    # TODO: discriminate between templates and user projects
    url = client.app.router["list_projects"].url_for()
    assert url == PREFIX + "/%s" % RESOURCE_NAME

    resp = await client.get(url)
    payload = await resp.json()
    assert resp.status == 200, payload

    projects, error = unwrap_envelope(payload)
    assert not error
    assert projects
    assert isinstance(projects, list)


async def test_read_one(client, fake_db, fake_project):
    pid = fake_project["projectUuid"]

    # get one
    url = client.app.router["get_project"].url_for(project_id=pid)
    assert url == PREFIX + "/%s/%s" % (RESOURCE_NAME, pid)

    resp = await client.get()
    payload = await resp.json()
    assert resp.status == 200, payload


async def test_update(client, fake_db, fake_project):
    fake_db.add_projects(fake_project, user_id=0) # TODO:
    pid = fake_project["projectUuid"]

    url = client.app.router["update_project"].url_for(project_id=pid)

    resp = await client.post(url, json={
        "name": "some other name",
        "description": "some other",
        "notes": "some other",
    })
    payload = await resp.json()
    assert resp.status == 200, payload

    # TODO: read in db

async def test_delete(client, fake_db, fake_project):
    resp = await client.post(PREFIX + "/%s/blackfynn" % RESOURCE_NAME)
    payload = await resp.json()

    assert resp.status == 204, payload
    assert not payload
