""" Covers user stories for ISAN : #501, #712, #730

"""
# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import textwrap
from copy import deepcopy
from pathlib import Path
from pprint import pprint
from typing import Dict

import pytest
from aiohttp import web

import simcore_service_webserver.statics
from servicelib.application import create_safe_application
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver import studies_access
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.statics import setup_statics
from simcore_service_webserver.studies_access import setup_studies_access
from simcore_service_webserver.users import setup_users
from utils_assert import assert_status
from utils_login import LoggedUser, UserRole
from utils_projects import NewProject, delete_all_projects

SHARED_STUDY_UUID = "e2e38eee-c569-4e55-b104-70d159e49c87"

@pytest.fixture
def qx_client_outdir(tmpdir, mocker):
    """  Emulates qx output at service/web/client after compiling """

    basedir = tmpdir.mkdir("source-output")
    folders = [ basedir.mkdir(folder_name) for folder_name in ('osparc', 'resource', 'transpiled')]

    index_file = Path( basedir.join("index.html") )
    index_file.write_text(textwrap.dedent("""\
    <!DOCTYPE html>
    <html>
    <body>
        <h1>OSPARC-SIMCORE</h1>
        <p> This is a result of qx_client_outdir fixture </p>
    </body>
    </html>
    """))

    # patch get_client_outdir
    mocker.patch.object(simcore_service_webserver.statics, "get_client_outdir")
    simcore_service_webserver.statics.get_client_outdir.return_value = Path(basedir)


@pytest.fixture
def client(loop, aiohttp_client, app_cfg, postgres_service, qx_client_outdir, monkeypatch):
#def client(loop, aiohttp_client, app_cfg, qx_client_outdir, monkeypatch): # <<<< FOR DEVELOPMENT. DO NOT REMOVE.
    cfg = deepcopy(app_cfg)

    cfg["db"]["init_tables"] = True # inits tables of postgres_service upon startup
    cfg['projects']['enabled'] = True
    cfg['storage']['enabled'] = False
    cfg['rabbit']['enabled'] = False

    app = create_safe_application(cfg)

    setup_statics(app)
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app) # TODO: why should we need this??
    setup_login(app)
    setup_users(app)
    assert setup_projects(app), "Shall not skip this setup"
    assert setup_studies_access(app), "Shall not skip this setup"

    # server and client
    yield loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': cfg["main"]["port"],
        'host': cfg['main']['host']
    }))


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
        await delete_all_projects(client.app)

@pytest.fixture
async def published_project(client, fake_project):
    project_data = deepcopy(fake_project)
    project_data["name"] = "Published project"
    project_data["uuid"] = SHARED_STUDY_UUID
    project_data["published"] = True

    async with NewProject(
        project_data,
        client.app,
        user_id=None,
        clear_all=True
    ) as template_project:
        yield template_project

@pytest.fixture
async def unpublished_project(client, fake_project):
    project_data = deepcopy(fake_project)
    project_data["name"] = "Tempalte Unpublished project"
    project_data["uuid"] = "'b134a337-a74f-40ff-a127-b36a1ccbede6"
    project_data["published"] = False

    async with NewProject(
        project_data,
        client.app,
        user_id=None,
        clear_all=True
    ) as template_project:
        yield template_project


async def _get_user_projects(client):
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(start=0, count=3, type="user"))
    payload = await resp.json()
    assert resp.status == 200, payload

    projects, error = unwrap_envelope(payload)
    assert not error, pprint(error)

    return projects

def _assert_same_projects(got: Dict, expected: Dict):
    # TODO: validate using api/specs/webserver/v0/components/schemas/project-v0.0.1.json
    # TODO: validate workbench!
    exclude = ["creationDate", "lastChangeDate", "prjOwner", "uuid", "workbench"]
    for key in expected.keys():
        if key not in exclude:
            assert got[key] == expected[key], "Failed in %s" % key


# TESTS --------------------------------------
async def test_access_to_invalid_study(client, published_project):
    resp = await client.get("/study/SOME_INVALID_UUID")
    content = await resp.text()

    assert resp.status == web.HTTPNotFound.status_code, str(content)


async def test_access_to_forbidden_study(client, unpublished_project):
    app = client.app

    valid_but_not_sharable = unpublished_project["uuid"]

    resp = await client.get("/study/%s" % valid_but_not_sharable)
    content = await resp.text()

    assert resp.status == web.HTTPNotFound.status_code, \
        "STANDARD studies are NOT sharable: %s" % content


async def test_access_study_anonymously(client, qx_client_outdir, published_project, storage_subsystem_mock):
    params = {
        "uuid":SHARED_STUDY_UUID,
        "name":"some-template"
    }

    url_path = "/study/%s" % SHARED_STUDY_UUID
    resp = await client.get(url_path)
    content = await resp.text()

    # index
    assert resp.status == web.HTTPOk.status_code, "Got %s" % str(content)
    assert str(resp.url.path) == "/"
    assert "OSPARC-SIMCORE" in content, \
        "Expected front-end rendering workbench's study, got %s" % str(content)

    real_url = str(resp.real_url)

    # has auto logged in as guest?
    resp = await client.get("/v0/me")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert data['login'].endswith("guest-at-osparc.io")
    assert data['gravatar_id']
    assert data['role'].upper() == UserRole.GUEST.name

    # guest user only a copy of the template project
    projects = await _get_user_projects(client)
    assert len(projects) == 1
    guest_project = projects[0]

    assert real_url.endswith("#/study/%s" % guest_project["uuid"])
    _assert_same_projects(guest_project, published_project)

    assert guest_project['prjOwner'] == data['login']


async def test_access_study_by_logged_user(client, logged_user, qx_client_outdir, published_project, storage_subsystem_mock):
    params = {
        "uuid":SHARED_STUDY_UUID,
        "name":"some-template"
    }

    url_path = "/study/%s" % SHARED_STUDY_UUID
    resp = await client.get(url_path)
    content = await resp.text()

    # returns index
    assert resp.status == web.HTTPOk.status_code, "Got %s" % str(content)
    assert str(resp.url.path) == "/"
    real_url = str(resp.real_url)

    assert "OSPARC-SIMCORE" in content, \
        "Expected front-end rendering workbench's study, got %s" % str(content)

    # user has a copy of the template project
    projects = await _get_user_projects(client)
    assert len(projects) == 1
    user_project = projects[0]

    # TODO: check redirects to /#/study/{uuid}
    assert real_url.endswith("#/study/%s" % user_project["uuid"])

    _assert_same_projects(user_project, published_project)

    assert user_project['prjOwner'] == logged_user['email']
