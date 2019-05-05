""" Covers user stories for ISAN : #501, #712, #730

"""
# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import textwrap
from pathlib import Path
from pprint import pprint
from typing import Dict

import pytest

import simcore_service_webserver.statics
from aiohttp import web
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.projects.projects_models import ProjectType
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.studies_access import (get_template_project,
                                                      setup_studies_access)
from simcore_service_webserver.users import setup_users
from utils_assert import assert_status
from utils_login import LoggedUser, UserRole
from utils_projects import NewProject

# Selection of core and tool services started in this swarm fixture (integration)
core_services = [
    'apihub',
    'postgres'
]

tool_services = [
    'adminer'
]


STUDY_UUID = "5461c746-4ef4-4c96-b4c4-77af8d08a82f"


@pytest.fixture
def webserver_service(loop, docker_stack, aiohttp_server, aiohttp_unused_port, api_specs_dir, app_config):
# DEVEL *do not delete* # def webserver_service(loop, aiohttp_server, aiohttp_unused_port, api_specs_dir, app_config):
    port = app_config["main"]["port"] = aiohttp_unused_port()
    app_config['main']['host'] = '127.0.0.1'

    app_config['storage']['enabled'] = False
    app_config['rabbit']['enabled'] = False

    app = web.Application()
    app[APP_CONFIG_KEY] = app_config
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app, debug=True)
    setup_login(app)
    setup_users(app)
    setup_projects(app,
        enable_fake_data=False, # no fake data
        disable_login=False
    )
    setup_studies_access(app)

    yield loop.run_until_complete( aiohttp_server(app, port=port) )

@pytest.fixture
def client(loop, webserver_service, aiohttp_client):
    client = loop.run_until_complete(aiohttp_client(webserver_service))
    yield client

@pytest.fixture
def qx_client_outdir(tmpdir, mocker):
    """  Emulates qx output at service/web/client after compiling """

    basedir = tmpdir.mkdir("source-output")
    folders = [ basedir.mkdir(folder_name) for folder_name in ('qxapp', 'resource', 'transpiled')]

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
    simcore_service_webserver.statics.get_client_outdir.return_value = basedir




# TESTS --------------------------------------
async def test_access_to_invalid_study(client):
    resp = await client.get("/study/SOME_INVALID_UUID")
    content = await resp.text()

    assert resp.status == web.HTTPNotFound.status_code, str(content)


async def test_access_to_forbidden_study(client):
    app = client.app
    params = {
        "uuid": STUDY_UUID,
        "type": ProjectType.STANDARD
    }

    async with NewProject(params, app) as expected_prj:

        resp = await client.get("/study/%s" % STUDY_UUID)
        content = await resp.text()

        assert resp.status == web.HTTPNotFound.status_code, \
            "STANDARD studies are NOT sharable: %s" % content


async def _get_user_projects(client):
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(start=0, count=3))
    payload = await resp.json()
    assert resp.status == 200, payload

    projects, error = unwrap_envelope(payload)
    assert not error, pprint(error)

    return projects

def _assert_same_projects(got: Dict, expected: Dict):
    for key in [k for k in expected.keys() if k!="uuid"]:
        assert got[key] == expected[key]


async def test_access_study_by_anonymous(client, qx_client_outdir):
    app = client.app
    params = {
        "uuid":STUDY_UUID,
        "name":"some-template"
    }

    async with NewProject(params, app) as expected_prj:

        url_path = "/study/%s" % STUDY_UUID
        resp = await client.get(url_path)
        content = await resp.text()

        # index
        assert resp.status == web.HTTPOk.status_code, "Got %s" % str(content)
        assert str(resp.url.path) == url_path
        assert "OSPARC-SIMCORE" in content, \
            "Expected front-end rendering workbench's study, got %s" % str(content)

        # has auto logged in as guest?
        resp = await client.get("/v0/me")
        data, _ = await assert_status(resp, web.HTTPOk)
        assert data['login'].endswith("guest-at-osparc.io")
        assert data['gravatar_id']
        assert data['role'].upper() == UserRole.ANONYMOUS.name

        # anonymous user only a copy of the template project
        projects = await _get_user_projects(client)
        assert len(projects) == 1
        got_prj = projects[0]

        _assert_same_projects(got_prj, expected_prj)



async def test_access_study_by_logged_user(client, qx_client_outdir):
    app = client.app
    params = {
        "uuid":STUDY_UUID,
        "name":"some-template"
    }

    async with LoggedUser(client):
        async with NewProject(params, app, clear_all=True) as expected_prj:

            url_path = "/study/%s" % STUDY_UUID
            resp = await client.get(url_path)
            content = await resp.text()

            # returns index
            assert resp.status == web.HTTPOk.status_code, "Got %s" % str(content)
            assert str(resp.url.path) == url_path
            assert "OSPARC-SIMCORE" in content, \
                "Expected front-end rendering workbench's study, got %s" % str(content)

            # user has a copy of the template project
            projects = await _get_user_projects(client)
            assert len(projects) == 1
            got_prj = projects[0]

            _assert_same_projects(got_prj, expected_prj)



async def test_devel(client):
    app = client.app
    params = {
        "uuid":STUDY_UUID,
        "name":"some-template"
    }

    async with NewProject(params, app) as expected_prj:

        prj = await get_template_project(app, STUDY_UUID)

        assert prj is not None
        assert prj["uuid"] == STUDY_UUID
        assert prj == expected_prj


#async def test_access_template_by_loggedin(client, ):
#    pass



#    # check if NO new anonymous user is created
