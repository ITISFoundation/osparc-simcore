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
from utils_projects import delete_all_projects

API_VERSION = "v0"
RESOURCE_NAME = 'projects'


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
    assert setup_projects(app,
        enable_fake_data=False, # no fake data
        disable_login=False
    )

    # server and client
    yield loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': port,
        'host': 'localhost'
    }))

    # teardown here ...


# Tests CRUD operations --------------------------------------------
PREFIX = "/" + API_VERSION

# TODO: template for CRUD testing?
# TODO: create parametrize fixture with resource_name


@pytest.mark.parametrize("role,expected", [
    (UserRole.ANONYMOUS, web.HTTPForbidden),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPCreated),
    (UserRole.TESTER, web.HTTPCreated),
    (UserRole.ADMIN, web.HTTPCreated),
])
async def test_create(client, fake_project, role, expected):
    url = client.app.router["create_projects"].url_for()
    assert str(url) == PREFIX + "/%s" % RESOURCE_NAME

    # POST /v0/projects
    async with LoggedUser(client, {'role': role.name} ) as user:
        resp = await client.post(url, json=fake_project)

        await assert_status(resp, expected)

        # TODO: validate response using OAS?


        # FIXME: cannot delete user until project is deleted
        # asyncpg.exceptions.ForeignKeyViolationError: update or delete on table "users"
        #   violates foreign key constraint "user_to_projects_user_id_fkey" on table "user_to_projects"
        await delete_all_projects(client.app[APP_DB_ENGINE_KEY])


# CRUD---------
#
# GET /v0/projects
# GET /v0/projects?type=template&start=0&count=3
# POST /v0/projects  {projec}

# GET /v0/projects/{project_id}
# PUT /v0/projects/{project_id}
# DELETE /v0/projects/{project_id}
