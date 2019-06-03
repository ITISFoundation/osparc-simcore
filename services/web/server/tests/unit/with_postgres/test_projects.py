# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import collections
import json
import uuid as uuidlib
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
from simcore_service_webserver.utils import now_str, to_datetime
from utils_assert import assert_status
from utils_login import LoggedUser
from utils_projects import NewProject, delete_all_projects

API_VERSION = "v0"
RESOURCE_NAME = 'projects'
API_PREFIX = "/" + API_VERSION


@pytest.fixture
def client(loop, aiohttp_client, aiohttp_unused_port, app_cfg, postgres_service):
#def client(loop, aiohttp_client, aiohttp_unused_port, app_cfg): # <<<< FOR DEVELOPMENT. DO NOT REMOVE.
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


@pytest.fixture
async def template_project(client, fake_project):
    async with NewProject(
        fake_project,
        client.app,
        user_id=None
    ) as template_prj:
        yield template_prj

def assert_replaced(current_project, update_data):
    def _extract(dikt, keys):
        return {k:dikt[k] for k in keys}

    modified = ["lastChangeDate", ]
    keep = [k for k in update_data.keys() if k not in modified]

    assert _extract(current_project, keep) == _extract(update_data, keep)

    k = "lastChangeDate"
    assert to_datetime(update_data[k]) < to_datetime(current_project[k])


# GET --------
@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_list_projects(client, logged_user, user_project, expected):
    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    assert str(url) == API_PREFIX + "/projects"

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

# POST --------
@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPCreated),
    (UserRole.TESTER, web.HTTPCreated),
])
async def test_new_project(client, logged_user, expected):
    # POST /v0/projects
    url = client.app.router["create_projects"].url_for()
    assert str(url) == API_PREFIX + "/projects"

    # Pre-defined fields imposed by required properties in schema
    default_project = {
        "uuid": "0000000",
        "name": "Minimal name",
        "description": "this description should not change",
        "prjOwner": "me",
        "creationDate": now_str(),
        "lastChangeDate": now_str(),
        "thumbnail": "None",
        "workbench":{}
    }

    resp = await client.post(url, json=default_project)

    data, error = await assert_status(resp, expected)

    if not error:
        new_project = data

        # updated fields
        assert default_project["uuid"] != new_project["uuid"]
        assert default_project["prjOwner"] != logged_user["name"]
        assert to_datetime(default_project["creationDate"]) < to_datetime(new_project["creationDate"])

        # invariant fields
        for key in new_project.keys():
            if key not in ('uuid', 'prjOwner', 'creationDate', 'lastChangeDate'):
                assert default_project[key] == new_project[key]

        # TODO: validate response using OAS?
        # FIXME: cannot delete user until project is deleted. See cascade  or too coupled??
        #  i.e. removing a user, removes all its projects!!

        # asyncpg.exceptions.ForeignKeyViolationError: update or delete on table "users"
        #   violates foreign key constraint "user_to_projects_user_id_fkey" on table "user_to_projects"
        await delete_all_projects(client.app[APP_DB_ENGINE_KEY])

@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPCreated),
    (UserRole.TESTER, web.HTTPCreated),
])
async def test_new_project_from_template(client, logged_user, template_project, expected):
    # POST /v0/projects?from_template={template_uuid}
    url = client.app.router["create_projects"].url_for().with_query(from_template=template_project["uuid"])

    resp = await client.post(url)

    data, error = await assert_status(resp, expected)

    if not error:
        project = data
        modified = ["prjOwner", "creationDate", "lastChangeDate", "uuid"]

        # different ownership
        assert project["prjOwner"] == logged_user["email"]
        assert project["prjOwner"] != template_project["prjOwner"]

        # different timestamps
        assert to_datetime(template_project["creationDate"]) < to_datetime(project["creationDate"])
        assert to_datetime(template_project["lastChangeDate"]) < to_datetime(project["lastChangeDate"])

        # different uuids for project and nodes!?
        assert project["uuid"] != template_project["uuid"]

        # check uuid replacement
        for node_name in project["workbench"]:
            try:
                uuidlib.UUID(node_name)
            except ValueError:
                pytest.fail("Invalid uuid in workbench node {}".format(node_name))

@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPCreated),
    (UserRole.TESTER, web.HTTPCreated),
])
async def test_new_project_from_template_with_body(client, logged_user, template_project, expected):
    # POST /v0/projects?from_template={template_uuid}
    url = client.app.router["create_projects"].url_for().with_query(from_template=template_project["uuid"])

    predefined = {
        "uuid":"",
        "name":"Sleepers8",
        "description":"Some lines from user",
        "thumbnail":"",
        "prjOwner":"",
        "creationDate":"2019-06-03T09:59:31.987Z",
        "lastChangeDate":"2019-06-03T09:59:31.987Z",
        "workbench":{}
    }

    resp = await client.post(url, json=predefined)

    data, error = await assert_status(resp, expected)

    if not error:
        project = data

        # uses predefined
        assert project["name"] == predefined["name"]
        assert project["description"] == predefined["description"]


        modified = ["prjOwner", "creationDate", "lastChangeDate", "uuid"]

        # different ownership
        assert project["prjOwner"] == logged_user["email"]
        assert project["prjOwner"] != template_project["prjOwner"]

        # different timestamps
        assert to_datetime(template_project["creationDate"]) < to_datetime(project["creationDate"])
        assert to_datetime(template_project["lastChangeDate"]) < to_datetime(project["lastChangeDate"])

        # different uuids for project and nodes!?
        assert project["uuid"] != template_project["uuid"]

        # check uuid replacement
        for node_name in project["workbench"]:
            try:
                uuidlib.UUID(node_name)
            except ValueError:
                pytest.fail("Invalid uuid in workbench node {}".format(node_name))

# PUT --------
@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_replace_project(client, logged_user, user_project, expected):
    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(project_id=user_project["uuid"])

    project_update = deepcopy(user_project)
    project_update["description"] = "some updated from original project!!!"

    resp = await client.put(url, json=project_update)
    data, error = await assert_status(resp, expected)

    if not error:
        assert_replaced(current_project=data, update_data=project_update)

@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_replace_project_updated_inputs(client, logged_user, user_project, expected):
    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(project_id=user_project["uuid"])

    project_update = deepcopy(user_project)
    #
    #"inputAccess": {
    #    "Na": "ReadAndWrite", <--------
    #    "Kr": "ReadOnly",
    #    "BCL": "ReadAndWrite",
    #    "NBeats": "ReadOnly",
    #    "Ligand": "Invisible",
    #    "cAMKII": "Invisible"
    #  },
    project_update["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]["inputs"]["Na"] = 55

    resp = await client.put(url, json=project_update)
    data, error = await assert_status(resp, expected)

    if not error:
        assert_replaced(current_project=data, update_data=project_update)

@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_replace_project_updated_readonly_inputs(client, logged_user, user_project, expected):
    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(project_id=user_project["uuid"])

    project_update = deepcopy(user_project)
    project_update["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]["inputs"]["Na"] = 55
    project_update["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]["inputs"]["Kr"] = 5

    resp = await client.put(url, json=project_update)
    data, error = await assert_status(resp, expected)

    if not error:
        assert_replaced(current_project=data, update_data=project_update)



# DELETE -------

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



# ######## DEVELOPMENT ###################################################
# import uuid
# from simcore_service_webserver.projects.projects_models import projects as projects_tbl
# from simcore_service_webserver.db_models import users as users_tbl
# from sqlalchemy import select

# from change_case import ChangeCase
# from aiopg.sa.exc import Error as DbError
# from psycopg2.errors import UniqueViolation


# @pytest.mark.skip("DEV")
# @pytest.mark.parametrize("user_role,expected", [
#     (UserRole.USER, web.HTTPOk),
# ])
# async def test_it(client, logged_user, user_project, expected):

#     db_engine = client.app[APP_DB_ENGINE_KEY]
#     tbl = projects_tbl


#     new_uuid = user_project["uuid"]
#     async with db_engine.acquire() as conn:
#         import pdb; pdb.set_trace()

#         try:
#             ins = tbl.insert().values({ChangeCase.camel_to_snake(k):v for k,v in user_project.items() if k!='id'})
#             await conn.execute(ins)
#         except UniqueViolation as ee:
#             import pdb; pdb.set_trace()
#         except DbError as ee:
#             import pdb; pdb.set_trace()

#         # try until found a unique uuid
#         while True:
#             result = await conn.execute(select([tbl.c.id])\
#                 .where(tbl.c.uuid==new_uuid))
#             found = await result.first()
#             if found:
#                 new_uuid = str(uuid.uuid1())
#             else: # is unique
#                 break

#         result = await conn.execute(select([users_tbl.c.email]).where(users_tbl.c.id==logged_user["id"]))
#         user_email = await result.first()
#         import pdb; pdb.set_trace()
#         assert user_email[0] == logged_user["email"]

#         result = await conn.execute(select([tbl]).where(tbl.c.uuid==user_project["uuid"]))
#         row = await result.first()
#         assert row
#         assert row[tbl.c.uuid] == user_project["uuid"]

#         result = await conn.execute(select([tbl]).where(tbl.c.uuid==new_uuid))
#         row = await result.first()
#         row = await result.fetchone()

#     # retrieve project
