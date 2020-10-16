""" Covers user stories for ISAN : #501, #712, #730

"""
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import re
import textwrap
from copy import deepcopy
from pathlib import Path
from pprint import pprint
from typing import Dict

import pytest
from aiohttp import ClientResponse, ClientSession, web
from models_library.projects import (
    Owner,
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    RunningState,
)
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser, UserRole
from pytest_simcore.helpers.utils_mock import future_with_result
from pytest_simcore.helpers.utils_projects import NewProject, delete_all_projects
from servicelib.application import create_safe_application
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver import catalog
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.products import setup_products
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.projects.projects_api import delete_project_from_db
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.settings import setup_settings
from simcore_service_webserver.statics import STATIC_DIRNAMES, setup_statics
from simcore_service_webserver.studies_access import setup_studies_access
from simcore_service_webserver.users import setup_users
from simcore_service_webserver.users_api import delete_user, is_user_guest

SHARED_STUDY_UUID = "e2e38eee-c569-4e55-b104-70d159e49c87"


@pytest.fixture
def qx_client_outdir(tmpdir):
    """  Emulates qx output at service/web/client after compiling """

    basedir = tmpdir.mkdir("source-output")
    folders = [basedir.mkdir(folder_name) for folder_name in STATIC_DIRNAMES]

    HTML = textwrap.dedent(
        """\
        <!DOCTYPE html>
        <html>
        <body>
            <h1>{0}-SIMCORE</h1>
            <p> This is a result of qx_client_outdir fixture for product {0}</p>
        </body>
        </html>
        """
    )

    index_file = Path(basedir.join("index.html"))
    index_file.write_text(HTML.format("OSPARC"))

    for folder, frontend_app in zip(folders, STATIC_DIRNAMES):
        index_file = Path(folder.join("index.html"))
        index_file.write_text(HTML.format(frontend_app.upper()))

    return Path(basedir)


@pytest.fixture
def mocks_on_projects_api(mocker) -> Dict:
    """
    All projects in this module are UNLOCKED
    """
    state = ProjectState(
        locked=ProjectLocked(
            value=False, owner=Owner(first_name="Speedy", last_name="Gonzalez")
        ),
        state=ProjectRunningState(value=RunningState.NOT_STARTED),
    ).dict(by_alias=True, exclude_unset=True)
    mocker.patch(
        "simcore_service_webserver.projects.projects_api.get_project_state_for_user",
        return_value=future_with_result(state),
    )


@pytest.fixture
def client(
    loop, aiohttp_client, app_cfg, postgres_db, qx_client_outdir, mocks_on_projects_api
):
    cfg = deepcopy(app_cfg)

    cfg["projects"]["enabled"] = True
    cfg["storage"]["enabled"] = False
    cfg["rabbit"]["enabled"] = False
    cfg["main"]["client_outdir"] = qx_client_outdir

    app = create_safe_application(cfg)

    setup_settings(app)
    setup_statics(app)
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)  # TODO: why should we need this??
    setup_login(app)
    setup_users(app)
    setup_products(app)
    assert setup_projects(app), "Shall not skip this setup"
    assert setup_studies_access(app), "Shall not skip this setup"

    # server and client
    yield loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={"port": cfg["main"]["port"], "host": cfg["main"]["host"]},
        )
    )


@pytest.fixture
async def logged_user(client):  # , role: UserRole):
    """adds a user in db and logs in with client

    NOTE: role fixture is defined as a parametrization below
    """
    role = UserRole.USER  # TODO: parameterize roles

    async with LoggedUser(
        client, {"role": role.name}, check_if_succeeds=role != UserRole.ANONYMOUS
    ) as user:

        yield user

        await delete_all_projects(client.app)


@pytest.fixture
async def published_project(client, fake_project) -> Dict:
    project_data = deepcopy(fake_project)
    project_data["name"] = "Published project"
    project_data["uuid"] = SHARED_STUDY_UUID
    project_data["published"] = True

    async with NewProject(
        project_data, client.app, user_id=None, clear_all=True
    ) as template_project:
        yield template_project


@pytest.fixture
async def unpublished_project(client, fake_project):
    project_data = deepcopy(fake_project)
    project_data["name"] = "Template Unpublished project"
    project_data["uuid"] = "b134a337-a74f-40ff-a127-b36a1ccbede6"
    project_data["published"] = False

    async with NewProject(
        project_data, client.app, user_id=None, clear_all=True
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
    exclude = set(
        [
            "creationDate",
            "lastChangeDate",
            "prjOwner",
            "uuid",
            "workbench",
            "accessRights",
        ]
    )
    for key in expected.keys():
        if key not in exclude:
            assert got[key] == expected[key], "Failed in %s" % key


async def assert_redirected_to_study(
    resp: ClientResponse, session: ClientSession
) -> str:
    content = await resp.text()
    assert resp.status == web.HTTPOk.status_code, f"Got {content}"

    # Expects redirection to osparc web (see qx_client_outdir fixture)
    assert resp.url.path == "/"
    assert (
        "OSPARC-SIMCORE" in content
    ), "Expected front-end rendering workbench's study, got %s" % str(content)

    # Expects auth cookie for current user
    assert "osparc.WEBAPI_SESSION" in [c.key for c in session.cookie_jar]

    # Expects fragment to indicate client where to find newly created project
    m = re.match(r"/study/([\d\w-]+)", resp.real_url.fragment)
    assert m, f"Expected /study/uuid, got {resp.real_url.fragment}"

    # returns newly created project
    redirected_project_id = m.group(1)
    return redirected_project_id


# TESTS --------------------------------------
async def test_access_to_invalid_study(client, published_project):
    resp = await client.get("/study/SOME_INVALID_UUID")
    content = await resp.text()

    assert resp.status == web.HTTPNotFound.status_code, str(content)


async def test_access_to_forbidden_study(client, unpublished_project):
    app = client.app

    valid_but_not_sharable = unpublished_project["uuid"]

    resp = await client.get("/study/valid_but_not_sharable")
    content = await resp.text()

    assert (
        resp.status == web.HTTPNotFound.status_code
    ), f"STANDARD studies are NOT sharable: {content}"


@pytest.fixture
async def catalog_subsystem_mock(monkeypatch, published_project):
    services_in_project = [
        {"key": s["key"], "version": s["version"]}
        for _, s in published_project["workbench"].items()
    ]

    async def mocked_get_services_for_user(*args, **kwargs):
        return services_in_project

    monkeypatch.setattr(
        catalog, "get_services_for_user_in_product", mocked_get_services_for_user
    )


async def test_access_study_anonymously(
    client,
    qx_client_outdir,
    published_project,
    storage_subsystem_mock,
    catalog_subsystem_mock,
):

    study_url = client.app.router["study"].url_for(id=published_project["uuid"])

    resp = await client.get(study_url)

    expected_prj_id = await assert_redirected_to_study(resp, client.session)

    # has auto logged in as guest?
    me_url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(me_url)

    data, _ = await assert_status(resp, web.HTTPOk)
    assert data["login"].endswith("guest-at-osparc.io")
    assert data["gravatar_id"]
    assert data["role"].upper() == UserRole.GUEST.name

    # guest user only a copy of the template project
    projects = await _get_user_projects(client)
    assert len(projects) == 1
    guest_project = projects[0]

    assert expected_prj_id == guest_project["uuid"]
    _assert_same_projects(guest_project, published_project)

    assert guest_project["prjOwner"] == data["login"]


async def test_access_study_by_logged_user(
    client,
    logged_user,
    qx_client_outdir,
    published_project,
    storage_subsystem_mock,
    catalog_subsystem_mock,
):
    study_url = client.app.router["study"].url_for(id=published_project["uuid"])
    resp = await client.get(study_url)
    await assert_redirected_to_study(resp, client.session)

    # user has a copy of the template project
    projects = await _get_user_projects(client)
    assert len(projects) == 1
    user_project = projects[0]

    # heck redirects to /#/study/{uuid}
    assert resp.real_url.fragment.endswith("/study/%s" % user_project["uuid"])
    _assert_same_projects(user_project, published_project)

    assert user_project["prjOwner"] == logged_user["email"]


async def test_access_cookie_of_expired_user(
    client,
    qx_client_outdir,
    published_project,
    storage_subsystem_mock,
    catalog_subsystem_mock,
):
    # emulates issue #1570
    app: web.Application = client.app

    study_url = app.router["study"].url_for(id=published_project["uuid"])
    resp = await client.get(study_url)

    await assert_redirected_to_study(resp, client.session)

    # Expects valid cookie and GUEST access
    me_url = app.router["get_my_profile"].url_for()
    resp = await client.get(me_url)

    data, _ = await assert_status(resp, web.HTTPOk)
    assert await is_user_guest(app, data["id"])

    async def garbage_collect_guest(uid):
        # Emulates garbage collector:
        #   - anonymous user expired, cleaning it up
        #   - client still holds cookie with its identifier nonetheless
        #
        assert await is_user_guest(app, uid)
        projects = await _get_user_projects(client)
        assert len(projects) == 1

        prj_id = projects[0]["uuid"]
        await delete_project_from_db(app, prj_id, uid)
        await delete_user(app, uid)
        return uid

    user_id = await garbage_collect_guest(uid=data["id"])
    user_email = data["login"]

    # Now this should be non -authorized
    resp = await client.get(me_url)
    await assert_status(resp, web.HTTPUnauthorized)

    # But still can access as a new user
    resp = await client.get(study_url)
    await assert_redirected_to_study(resp, client.session)

    # as a guest user
    resp = await client.get(me_url)
    data, _ = await assert_status(resp, web.HTTPOk)
    assert await is_user_guest(app, data["id"])

    # But I am another user
    assert data["id"] != user_id
    assert data["login"] != user_email
