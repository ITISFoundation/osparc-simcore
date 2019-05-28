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
from simcore_service_webserver.db import APP_DB_ENGINE_KEY, setup_db
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from utils_assert import assert_status
from utils_login import LoggedUser
from utils_projects import NewProject, delete_all_projects

API_VERSION = "v0"
RESOURCE_NAME = 'projects'
API_PREFIX = "/" + API_VERSION


@pytest.fixture
def client(loop, aiohttp_client, aiohttp_unused_port, app_cfg, postgres_service):
#def client(loop, aiohttp_client, aiohttp_unused_port, app_cfg):
    app = web.Application()

    # config app
    port = app_cfg["main"]["port"] = aiohttp_unused_port()
    app_cfg["db"]["init_tables"] = True # inits tables of postgres_service upon startup
    app_cfg["projects"]["enabled"] = True

    app[APP_CONFIG_KEY] = app_cfg

    # setup app
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app, debug=True)
    setup_login(app)            # needed for login_utils fixtures
    assert setup_projects(app)

    # server and client
    yield loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': port,
        'host': 'localhost'
    }))

    # teardown here ...

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
async def user_project(client, fake_project, logged_user):
    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"]
    ) as project:
        yield project


# Tests CRUD operations --------------------------------------------
# TODO: template for CRUD testing?

@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_list_projects(client, logged_user, user_project, expected):
    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    assert str(url) == API_PREFIX + "/" + RESOURCE_NAME

    resp = await client.get(url)
    data, errors = await assert_status(resp, expected)

    #TODO: GET /v0/projects?type=user

    if not errors:
        assert len(data) == 1
        assert data[0] == user_project

@pytest.mark.skip("TODO")
async def test_list_templates_only(client, logged_user, user_project, expected):
    #TODO: GET /v0/projects?type=template
    #TODO: GET /v0/projects?type=template&start=0&count=3
    pass




@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPCreated),
    (UserRole.TESTER, web.HTTPCreated),
])
async def test_create_project(client, fake_project, logged_user, expected):
    # POST /v0/projects
    url = client.app.router["create_projects"].url_for()
    assert str(url) == API_PREFIX + "/" + RESOURCE_NAME

    # NOTE: This case is not used in the UI. Remove???
    resp = await client.post(url, json=fake_project)

    await assert_status(resp, expected)

    # TODO: validate response using OAS?
    # FIXME: cannot delete user until project is deleted. See cascade ,
    #  i.e. removing a user, removes all its projects!!

    # asyncpg.exceptions.ForeignKeyViolationError: update or delete on table "users"
    #   violates foreign key constraint "user_to_projects_user_id_fkey" on table "user_to_projects"
    await delete_all_projects(client.app[APP_DB_ENGINE_KEY])


@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_get_project(client, logged_user, user_project, expected):
    # GET /v0/projects/{project_id}
    url = client.app.router["get_project"].url_for(project_id=user_project["uuid"])

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert data == user_project


@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_replace_project(client, logged_user, user_project, expected):
    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(project_id=user_project["uuid"])

    updated_project = deepcopy(user_project)
    updated_project["description"] = "some different"

    resp = await client.put(url, json=updated_project)
    data, error = await assert_status(resp, expected)

    if not error:
        assert data == updated_project


@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPNoContent),
    (UserRole.TESTER, web.HTTPNoContent),
])
async def test_delete_project(client, logged_user, user_project, expected):
    # DELETE /v0/projects/{project_id}
    url = client.app.router["delete_project"].url_for(project_id=user_project["uuid"])

    resp = await client.delete(url)
    await assert_status(resp, expected)



# POST /projects variants --------------------------------------
@pytest.mark.skip("TODO: under dev")
async def test_new_project_with_predefined_fields(client, fake_project, logged_user, expected):
    # POST /v0/projects
    #   optional body with predefined fields, e.g. { name='foo', description,... }
    # -->

    #"uuid",
    #"prjOwner",
    #"creationDate",
    #"lastChangeDate",

    pass


@pytest.mark.skip("TODO: under dev")
async def test_new_project_from_template(client, logged_user, template_project, expected):
    # POST /v0/projects?from_template={template_uuid}
    #
    pass


@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_replace_project_workbench_inputs(client, logged_user, user_project, expected):
    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(project_id=user_project["uuid"])

    updated_project = deepcopy(user_project)
    #
    #"inputAccess": {
    #    "Na": "ReadAndWrite", <--------
    #    "Kr": "ReadOnly",
    #    "BCL": "ReadAndWrite",
    #    "NBeats": "ReadOnly",
    #    "Ligand": "Invisible",
    #    "cAMKII": "Invisible"
    #  },
    updated_project["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]["inputs"]["Na"] = 55

    resp = await client.put(url, json=updated_project)
    data, error = await assert_status(resp, expected)

    if not error:
        assert data == updated_project


@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_update_project_workbench_readonly_inputs(client, logged_user, user_project, expected):
    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(project_id=user_project["uuid"])

    updated_project = deepcopy(user_project)
    updated_project["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]["inputs"]["Na"] = 55
    updated_project["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]["inputs"]["Kr"] = 5

    resp = await client.put(url, json=updated_project)
    data, error = await assert_status(resp, expected)

    if not error:
        assert data == updated_project
