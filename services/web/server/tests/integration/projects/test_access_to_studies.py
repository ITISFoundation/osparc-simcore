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
import simcore_service_webserver.studies_access
from aiohttp import web
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver import studies_access
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.projects.projects_models import ProjectType
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.statics import setup_statics
from simcore_service_webserver.studies_access import (TEMPLATE_PREFIX,
                                                      get_template_project,
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


STUDY_UUID = TEMPLATE_PREFIX + "THIS_IS_A_FAKE_STUDY_FOR_TESTING_UUID"


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
    simcore_service_webserver.statics.get_client_outdir.return_value = Path(basedir)


@pytest.fixture
def webserver_service(loop, docker_stack, aiohttp_server, aiohttp_unused_port, api_specs_dir, app_config, qx_client_outdir):
##def webserver_service(loop, aiohttp_server, aiohttp_unused_port, api_specs_dir, app_config, qx_client_outdir): # <<=======OFFLINE DEV
    port = app_config["main"]["port"] = aiohttp_unused_port()
    app_config['main']['host'] = '127.0.0.1'

    app_config['storage']['enabled'] = False
    app_config['rabbit']['enabled'] = False

    app = web.Application()
    app[APP_CONFIG_KEY] = app_config
    setup_statics(app)
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app, debug=True) # TODO: why should we need this??
    setup_login(app)
    setup_users(app)
    setup_projects(app,
        enable_fake_data=False, # no fake data
        disable_login=False
    )
    setup_studies_access(app)

    yield loop.run_until_complete( aiohttp_server(app, port=port) )


@pytest.fixture
def client(loop, webserver_service, aiohttp_client, monkeypatch):
    client = loop.run_until_complete(aiohttp_client(webserver_service))

    assert studies_access.SHARABLE_TEMPLATE_STUDY_IDS, "Did u change the name again?"
    monkeypatch.setattr(studies_access, 'SHARABLE_TEMPLATE_STUDY_IDS', [STUDY_UUID, ])

    yield client






# TESTS --------------------------------------
async def test_access_to_invalid_study(client):
    resp = await client.get("/study/SOME_INVALID_UUID")
    content = await resp.text()

    assert resp.status == web.HTTPNotFound.status_code, str(content)


async def test_access_to_forbidden_study(client):
    app = client.app

    VALID_BUT_NON_SHARABLE_STUDY_UUID = "8402b4e0-3659-4e36-bc26-c4312f02f05f"
    params = {
        "uuid": VALID_BUT_NON_SHARABLE_STUDY_UUID
    }

    async with NewProject(params, app) as expected_prj:

        resp = await client.get("/study/%s" % VALID_BUT_NON_SHARABLE_STUDY_UUID)
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
    # TODO: validate using api/specs/webserver/v0/components/schemas/project-v0.0.1.json
    # TODO: validate workbench!
    PROPERTIES_TO_CHECK =  [
        "name",
        "description",
        "creationDate",
        "lastChangeDate",
        "thumbnail"
    ]
    for key in PROPERTIES_TO_CHECK:
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
        assert str(resp.url.path) == "/"
        assert "OSPARC-SIMCORE" in content, \
            "Expected front-end rendering workbench's study, got %s" % str(content)

        real_url = str(resp.real_url)

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

        assert real_url.endswith("#/study/%s" % got_prj["uuid"])
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
            assert str(resp.url.path) == "/"
            real_url = str(resp.real_url)

            assert "OSPARC-SIMCORE" in content, \
                "Expected front-end rendering workbench's study, got %s" % str(content)

            # user has a copy of the template project
            projects = await _get_user_projects(client)
            assert len(projects) == 1
            got_prj = projects[0]

            # TODO: check redirects to /#/study/{uuid}
            assert real_url.endswith("#/study/%s" % got_prj["uuid"])

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
