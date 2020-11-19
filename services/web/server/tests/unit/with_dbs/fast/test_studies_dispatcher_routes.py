# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import re
from copy import deepcopy
from pprint import pprint
from typing import Dict

import pytest
from aiohttp import ClientResponse, ClientSession, web
from yarl import URL

from models_library.projects_state import (
    Owner,
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    RunningState,
)
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserRole
from pytest_simcore.helpers.utils_mock import future_with_result
from simcore_service_webserver import catalog
from simcore_service_webserver.log import setup_logging


@pytest.fixture
def app_cfg(default_app_cfg, aiohttp_unused_port, qx_client_outdir, redis_service):
    """App's configuration used for every test in this module

    NOTE: Overrides services/web/server/tests/unit/with_dbs/conftest.py::app_cfg to influence app setup
    """
    cfg = deepcopy(default_app_cfg)

    cfg["main"]["port"] = aiohttp_unused_port()
    cfg["main"]["client_outdir"] = str(qx_client_outdir)
    cfg["main"]["studies_access_enabled"] = True

    exclude = {
        "tracing",
        "director",
        "smtp",
        "storage",
        "activity",
        "diagnostics",
        "groups",
        "tags",
        "publications",
        "catalog",
        "computation",
    }
    include = {
        "db",
        "rest",
        "projects",
        "login",
        "socketio",
        "resource_manager",
        "users",
        "studies_access",
        "products",
        "studies_dispatcher",
    }

    assert include.intersection(exclude) == set()

    for section in include:
        cfg[section]["enabled"] = True
    for section in exclude:
        cfg[section]["enabled"] = False

    # NOTE: To see logs, use pytest -s --log-cli-level=DEBUG
    setup_logging(level=logging.DEBUG)

    # Enforces smallest GC in the background task
    cfg["resource_manager"]["garbage_collection_interval_seconds"] = 1

    return cfg


# REST-API -----------------------------------------------------------------------------------------------
#  Samples taken from trials on http://127.0.0.1:9081/dev/doc#/viewer/get_viewer_for_file
#


def _get_base_url(client) -> str:
    s = client.server
    return str(URL.build(scheme=s.scheme, host=s.host, port=s.port))


async def test_api_get_viewer_for_file(client):
    resp = await client.get("/v0/viewers?file_type=DICOM&file_name=foo&file_size=10000")
    data, error = await assert_status(resp, web.HTTPOk)

    base_url = _get_base_url(client)
    assert await resp.json() == {
        "data": {
            "file_type": "DICOM",
            "viewer_title": "Sim4life v1.0.16",
            "redirection_url": f"{base_url}/view?file_type=DICOM&file_name=foo&file_size=10000",
        },
        "error": None,
    }


async def test_api_get_viewer_for_unsupported_type(client):
    resp = await client.get("/v0/viewers?file_type=UNSUPPORTED_TYPE")
    data, error = await assert_status(resp, web.HTTPUnprocessableEntity)

    assert await resp.json() == {
        "data": None,
        "error": {
            "logs": [
                {
                    "message": "No viewer available for file type 'UNSUPPORTED_TYPE''",
                    "level": "ERROR",
                    "logger": "user",
                }
            ],
            "errors": [
                {
                    "code": "HTTPUnprocessableEntity",
                    "message": "No viewer available for file type 'UNSUPPORTED_TYPE''",
                    "resource": None,
                    "field": None,
                }
            ],
            "status": 422,
        },
    }


async def test_api_list_supported_filetypes(client):
    resp = await client.get("/v0/viewers/filetypes")
    data, error = await assert_status(resp, web.HTTPOk)

    base_url = _get_base_url(client)
    assert await resp.json() == {
        "data": [
            {
                "file_type": "DICOM",
                "viewer_title": "Sim4life v1.0.16",
                "redirection_url": f"{base_url}/view?file_type=DICOM",
            },
            {
                "file_type": "CSV",
                "viewer_title": "2d plot - rawgraphs v2.10.6",
                "redirection_url": f"{base_url}/view?file_type=CSV",
            },
        ],
        "error": None,
    }


# REDIRECT ROUTES --------------------------------------------------------------------------------


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


@pytest.fixture
def mocks_on_projects_api(mocker) -> Dict:
    """
    All projects in this module are UNLOCKED
    """
    state = ProjectState(
        locked=ProjectLocked(
            value=False,
            owner=Owner(user_id=2, first_name="Speedy", last_name="Gonzalez"),
        ),
        state=ProjectRunningState(value=RunningState.NOT_STARTED),
    ).dict(by_alias=True, exclude_unset=True)
    mocker.patch(
        "simcore_service_webserver.projects.projects_api.get_project_state_for_user",
        return_value=future_with_result(state),
    )


async def _get_user_projects(client):
    from servicelib.rest_responses import unwrap_envelope

    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(type="user"))

    payload = await resp.json()
    assert resp.status == 200, payload

    projects, error = unwrap_envelope(payload)
    assert not error, pprint(error)

    return projects


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

    ### FIXME!!

    # Expects fragment to indicate client where to find newly created project
    m = re.match(r"/view/([\d\w-]+)", resp.real_url.fragment)
    assert m, f"Expected /study/uuid, got {resp.real_url.fragment}"

    # returns newly created project
    redirected_project_id = m.group(1)
    return redirected_project_id


@pytest.mark.xfail()
async def test_viewer_redirect_with_errors(client):
    resp = await client.get(
        r"/view?file_type=DICOM&file_size=1&file_name=foo&download_link=http%3A%2F%2Fhttpbin.org%2Fimage%2Fjpeg"
    )

    base_url = str(client.app.base_url)
    expected_redirect_url = f"{base_url}/#/error?message=Ups+something+went+wrong+while+processing+your+request"


@pytest.mark.xfail()
async def test_dispatch_viewer_anonymously(
    client,
    storage_subsystem_mock,
    catalog_subsystem_mock,
    mocks_on_projects_api,
):

    redirect_url = (
        client.app.router["get_redirection_to_viewer"]
        .url_for()
        .with_query(
            file_name="foo",
            file_size=3,
            file_type="CSV",
            download_link="https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/8987c95d0ca0090e14f3a5b52db724fa24114cf5/services/storage/tests/data/users.csv",
        )
    )

    resp = await client.get(redirect_url)

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
    assert guest_project["prjOwner"] == data["login"]



def test_map_file_types_to_viewers():
    pass


def test_create_guest_user():
    pass


def test_portal_workflow():
    pass
