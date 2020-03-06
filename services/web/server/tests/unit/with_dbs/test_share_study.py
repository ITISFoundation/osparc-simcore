# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.share_study import setup_share_study
from utils_assert import assert_status
from utils_login import LoggedUser
from utils_projects import NewProject

API_VERSION = "v0"
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
    setup_rest(app)
    setup_login(app)            # needed for login_utils fixtures
    setup_projects(app)
    setup_share_study(app)

    # server and client
    yield loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': port,
        'host': 'localhost'
    }))

    # teardown here ...

@pytest.fixture()
async def logged_user(client, user_role: UserRole):
    """ adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds = user_role!=UserRole.ANONYMOUS
    ) as user:
        print("-----> logged in user", user_role)
        yield user
        print("<----- logged out user", user_role)

@pytest.fixture
async def user_project(client, fake_project, logged_user):
    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"]
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.mark.parametrize("user_role,expected", [
    (UserRole.USER, web.HTTPOk)
])
@pytest.mark.skip(reason="This should go into integration test. Paused until it gets refactored")
async def test_get_shared(client, logged_user, user_project, expected):
    study_id = user_project["uuid"]
    assert study_id

    url = API_PREFIX + "/share/study/" + study_id
    assert url

    resp = await client.get(url)
    data, _errors = await assert_status(resp, expected)

    assert study_id in data.get('copyLink')
    assert study_id in data.get('copyToken')
    assert type(data.get('copyObject')) is dict


@pytest.mark.parametrize("user_role,expected", [
    (UserRole.USER, web.HTTPOk)
])
@pytest.mark.skip(reason="This should go into integration test. Paused until it gets refactored")
async def test_get_shared_study_with_token(client, logged_user, user_project, expected):
    study_id = user_project["uuid"]
    url = API_PREFIX + "/share/study/" + study_id
    resp = await client.get(url)
    data, _errors = await assert_status(resp, web.HTTPOk)

    token = data.get('copyToken')
    url = API_PREFIX + "/shared/study/" + token
    assert url

    resp = await client.get(url)
    data, _errors = await assert_status(resp, web.HTTPOk)

    assert data
