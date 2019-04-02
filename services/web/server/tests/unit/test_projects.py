# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import collections
from copy import deepcopy

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
from simcore_service_webserver.projects.projects_handlers import Fake


API_VERSION = "v0"
RESOURCE_NAME = 'projects'
ANONYMOUS_UID = -1 # For testing purposes

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
    setup_projects(app,
        enable_fake_data=False, # no fake data
        disable_login=True
    )

    yield loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )


@pytest.fixture
def fake_project():
    # TODO: create automatically fakes??
    #
    # generated from api/specs/webserver/v0/components/schemas/project-v0.0.1.json
    # using http://json-schema-faker.js.org/
    return {
        "uuid": "f298d06b-707a-6257-a462-d7bf73b76c0c",
        "name": "ex",
        "description": "anim sint pariatur do dolore",
        "notes": "enim nisi consequat",
        "prjOwner": "dolore ad do consectetur",
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
    # TODO: create fixture
    pid = fake_project["uuid"]
    #--------------------------

    url = client.app.router["create_projects"].url_for()
    assert str(url) == PREFIX + "/%s" % RESOURCE_NAME

    # POST /v0/projects
    resp = await client.post(url, json=fake_project)
    text = await resp.text()

    payload = await resp.json()
    assert resp.status == 201, payload
    project, error = unwrap_envelope(payload)
    # TODO:  there is no need to return data since everything is decided upon request

    assert not error

    assert len(fake_db.projects)==1
    assert fake_db.projects[pid].data == fake_project
    assert pid in fake_db.user_to_projects_map[ANONYMOUS_UID]


async def test_list(client, fake_db):
    # TODO: create fixture
    fake_db.load_user_projects(ANONYMOUS_UID)
    fake_db.load_template_projects()
    #-----------------

    # list all user projects
    url = client.app.router["list_projects"].url_for()
    assert str(url) == PREFIX + "/%s" % RESOURCE_NAME

    # GET /v0/projects
    resp = await client.get(url.with_query(start=1, count=2))
    payload = await resp.json()
    assert resp.status == 200, payload

    projects, error = unwrap_envelope(payload)
    assert not error
    assert projects
    assert len(projects)==2

    # list all template projects
    resp = await client.get(url.with_query(type="template"))
    payload = await resp.json()
    assert resp.status == 200, payload

    projects, error = unwrap_envelope(payload)
    assert not error
    # fake-template-projects.json + fake-template-projects.osparc.json
    assert len(projects) == 5 + 1




async def test_get(client, fake_db, fake_project):
    fake_db.add_projects([fake_project, ], user_id=ANONYMOUS_UID) # TODO: create fixture
    pid = fake_project["uuid"]
    #-----------------

    # get one
    url = client.app.router["get_project"].url_for(project_id=pid)
    assert str(url) == PREFIX + "/%s/%s" % (RESOURCE_NAME, pid)

    # GET /v0/projects/{project_id}
    resp = await client.get(url)
    payload = await resp.json()
    assert resp.status == 200, payload

    project, error = unwrap_envelope(payload)
    assert not error
    assert project

    assert project == fake_project


async def test_update(client, fake_db, fake_project):
    fake_db.add_projects([fake_project, ], user_id=ANONYMOUS_UID) # TODO: create fixture
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

    url = client.app.router["replace_project"].url_for(project_id=pid)
    assert str(url) == PREFIX + "/%s/%s" % (RESOURCE_NAME, pid)

    # PUT /v0/projects/{project_id}
    modified = deepcopy(fake_project)
    modified["name"] = "some other name"
    modified["description"] = "some other"
    modified["notes"] = "some other"
    modified["workbench"]["newname"] = modified["workbench"].pop("Xw)F")

    resp = await client.put(url, json=modified)
    payload = await resp.json()
    assert resp.status == 200, payload

    project, error = unwrap_envelope(payload)
    assert not error
    assert not project

    assert fake_db.projects[pid].data["name"] == "some other name"
    assert fake_db.projects[pid].data["notes"] == "some other"
    assert "newname" in fake_db.projects[pid].data["workbench"]
    assert fake_db.projects[pid].data["workbench"]["newname"] == fake_project["workbench"]["Xw)F"]



async def test_delete(client, fake_db, fake_project):
    fake_db.add_projects([fake_project, ], user_id=ANONYMOUS_UID) # TODO:
    pid = fake_project["uuid"]
    # -------------

    url = client.app.router["delete_project"].url_for(project_id=pid)
    assert str(url) == PREFIX + "/%s/%s" % (RESOURCE_NAME, pid)

    # DELETE /v0/projects/{project_id}
    resp = await client.delete(url)
    payload = await resp.json()

    assert resp.status == 204, payload

    data, error = unwrap_envelope(payload)
    assert not data
    assert not error

    assert not fake_db.projects
    assert not fake_db.user_to_projects_map


async def test_delete_invalid_project(client, fake_db):
    resp = await client.delete("/v0/projects/some-fake-id")
    payload = await resp.json()

    assert resp.status == 204, payload
    data, error = unwrap_envelope(payload)
    assert not data
    assert not error


async def test_workflow(client, fake_db, fake_project):
    fake_db.add_projects([fake_project, ], user_id=ANONYMOUS_UID) # TODO: create fixture
    #-----------------

   # list all user projects

    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(start=0, count=3))
    payload = await resp.json()
    assert resp.status == 200, payload

    projects, error = unwrap_envelope(payload)
    assert not error
    assert projects

    #-------------------------------------------------
    modified = deepcopy(projects[0])
    pid = modified["uuid"]

    modified["name"] = "some other name"
    modified["notes"] = "some other"
    modified["workbench"]["ReNamed"] =  modified["workbench"].pop("Xw)F")
    modified["workbench"]["ReNamed"]["position"]["x"] = 0.0

    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(project_id=pid)
    resp = await client.put(url, json=modified)
    payload = await resp.json()
    assert resp.status == 200, payload

    project, error = unwrap_envelope(payload)
    assert not error
    assert not project

    # -------------------------
    # GET /v0/projects/{project_id}
    url = client.app.router["get_project"].url_for(project_id=pid)
    resp = await client.get(url)
    payload = await resp.json()
    assert resp.status == 200, payload
    project, error = unwrap_envelope(payload)

    assert project["name"] == "some other name"
    assert project["notes"] == "some other"
    assert "ReNamed" in project["workbench"]
    assert "Xw)F" not in project["workbench"]

    assert project == modified




#-----------------------------------
@pytest.mark.skip(reason="Handlers still not implemented")
async def test_nodes_api(client):
    params= {
        'nodeInstanceUUID': '12345',
        'outputKey': 'foo',
        'apiCall': 'bar'
    }
    api = {}

    url = "/nodes/{nodeInstanceUUID}/outputUi/{outputKey}".format(**params)
    resp = await client.get(url)

    url = "/nodes/{nodeInstanceUUID}/outputUi/{outputKey}/{apiCall}".format(**params)
    resp = await client.post(url, json=api)

    url = "/nodes/{nodeInstanceUUID}/iframe".format(**params)
    resp = await client.get(url)
