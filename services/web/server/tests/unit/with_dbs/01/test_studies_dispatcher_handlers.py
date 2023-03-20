# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import re
import urllib.parse
from copy import deepcopy
from pprint import pprint
from typing import Iterator

import pytest
import sqlalchemy as sa
from aiohttp import ClientResponse, ClientSession, web
from aioresponses import aioresponses
from models_library.projects_state import ProjectLocked, ProjectStatus
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserRole
from simcore_service_webserver import catalog
from simcore_service_webserver.log import setup_logging
from simcore_service_webserver.studies_dispatcher._core import ViewerInfo
from sqlalchemy.sql import text
from yarl import URL


@pytest.fixture
def inject_tables(postgres_db: sa.engine.Engine):

    stmt_create_services = text(
        'INSERT INTO "services_meta_data" ("key", "version", "owner", "name", "description", "thumbnail", "classifiers", "created", "modified", "quality") VALUES'
        "('simcore/services/dynamic/raw-graphs',	'2.11.1',	NULL,	'2D plot',	'2D plots powered by RAW Graphs',	NULL,	'{}',	'2021-03-02 16:08:28.655207',	'2021-03-02 16:08:28.655207',	'{}'),"
        "('simcore/services/dynamic/bio-formats-web',	'1.0.1',	NULL,	'bio-formats',	'Bio-Formats image viewer',	'https://www.openmicroscopy.org/img/logos/bio-formats.svg',	'{}',	'2021-03-02 16:08:28.420722',	'2021-03-02 16:08:28.420722',	'{}'),"
        "('simcore/services/dynamic/jupyter-octave-python-math',	'1.6.9',	NULL,	'JupyterLab Math',	'JupyterLab Math with octave and python',	NULL,	'{}',	'2021-03-02 16:08:28.420722',	'2021-03-02 16:08:28.420722',	'{}');"
    )
    stmt_create_services_consume_filetypes = text(
        'INSERT INTO "services_consume_filetypes" ("service_key", "service_version", "service_display_name", "service_input_port", "filetype", "preference_order", "is_guest_allowed") VALUES'
        "('simcore/services/dynamic/bio-formats-web',	'1.0.1',	'bio-formats',	'input_1',	'PNG',	0, '1'),"
        "('simcore/services/dynamic/raw-graphs',	'2.11.1',	'RAWGraphs',	'input_1',	'CSV',	0, '1'),"
        "('simcore/services/dynamic/bio-formats-web',	'1.0.1',	'bio-formats',	'input_1',	'JPEG',	0, '1'),"
        "('simcore/services/dynamic/raw-graphs',	'2.11.1',	'RAWGraphs',	'input_1',	'TSV',	0, '1'),"
        "('simcore/services/dynamic/raw-graphs',	'2.11.1',	'RAWGraphs',	'input_1',	'XLSX',	0, '1'),"
        "('simcore/services/dynamic/raw-graphs',	'2.11.1',	'RAWGraphs',	'input_1',	'JSON',	0, '1'),"
        "('simcore/services/dynamic/jupyter-octave-python-math',	'1.6.9',	'JupyterLab Math',	'input_1',	'PY',	0, '0'),"
        "('simcore/services/dynamic/jupyter-octave-python-math',	'1.6.9',	'JupyterLab Math',	'input_1',	'IPYNB',0, '0');"
    )
    with postgres_db.connect() as conn:
        conn.execute(stmt_create_services)
        conn.execute(stmt_create_services_consume_filetypes)


FAKE_VIEWS_LIST = [
    ViewerInfo(
        key="simcore/services/dynamic/raw-graphs",
        version="2.11.1",
        filetype="CSV",
        label="RAWGraphs",
        input_port_key="input_1",
    ),
    ViewerInfo(
        key="simcore/services/dynamic/bio-formats-web",
        version="1.0.1",
        filetype="JPEG",
        label="bio-formats",
        input_port_key="input_1",
    ),
    ViewerInfo(
        key="simcore/services/dynamic/raw-graphs",
        version="2.11.1",
        filetype="JSON",
        label="RAWGraphs",
        input_port_key="input_1",
    ),
    ViewerInfo(
        key="simcore/services/dynamic/bio-formats-web",
        version="1.0.1",
        filetype="PNG",
        label="bio-formats",
        input_port_key="input_1",
    ),
    ViewerInfo(
        key="simcore/services/dynamic/raw-graphs",
        version="2.11.1",
        filetype="TSV",
        label="RAWGraphs",
        input_port_key="input_1",
    ),
    ViewerInfo(
        key="simcore/services/dynamic/raw-graphs",
        version="2.11.1",
        filetype="XLSX",
        label="RAWGraphs",
        input_port_key="input_1",
    ),
    ViewerInfo(
        key="simcore/services/dynamic/jupyter-octave-python-math",
        version="1.6.9",
        filetype="PY",
        label="JupyterLab Math",
        input_port_key="input_1",
    ),
    ViewerInfo(
        key="simcore/services/dynamic/jupyter-octave-python-math",
        version="1.6.9",
        filetype="INBPY",
        label="JupyterLab Math",
        input_port_key="input_1",
    ),
]


@pytest.fixture
def app_cfg(
    default_app_cfg,
    unused_tcp_port_factory,
    redis_service: URL,
    inject_tables,
):
    """App's configuration used for every test in this module

    NOTE: Overrides services/web/server/tests/unit/with_dbs/conftest.py::app_cfg to influence app setup
    """
    cfg = deepcopy(default_app_cfg)

    cfg["main"]["port"] = unused_tcp_port_factory()
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
        "clusters",
    }
    include = {
        "db",
        "rest",
        "projects",
        "login",
        "socketio",
        "resource_manager",
        "users",
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


@pytest.fixture(autouse=True)
async def director_v2_automock(
    director_v2_service_mock: aioresponses,
) -> Iterator[aioresponses]:
    yield director_v2_service_mock


# REST-API -----------------------------------------------------------------------------------------------
#  Samples taken from trials on http://127.0.0.1:9081/dev/doc#/viewer/get_viewer_for_file
#


def _get_base_url(client) -> str:
    s = client.server
    return str(URL.build(scheme=s.scheme, host=s.host, port=s.port))


async def test_api_get_viewer_for_file(client):

    resp = await client.get("/v0/viewers/default?file_type=JPEG")
    data, _ = await assert_status(resp, web.HTTPOk)

    base_url = _get_base_url(client)
    assert data == [
        {
            "file_type": "JPEG",
            "title": "Bio-formats v1.0.1",
            "view_url": f"{base_url}/view?file_type=JPEG&viewer_key=simcore/services/dynamic/bio-formats-web&viewer_version=1.0.1",
        },
    ]


async def test_api_get_viewer_for_unsupported_type(client):
    resp = await client.get("/v0/viewers/default?file_type=UNSUPPORTED_TYPE")
    data, error = await assert_status(resp, web.HTTPOk)
    assert data == []
    assert error is None


async def test_api_list_supported_filetypes(client):

    resp = await client.get("/v0/viewers/default")
    data, _ = await assert_status(resp, web.HTTPOk)

    base_url = _get_base_url(client)
    assert data == [
        {
            "title": "Rawgraphs v2.11.1",
            "file_type": "CSV",
            "view_url": f"{base_url}/view?file_type=CSV&viewer_key=simcore/services/dynamic/raw-graphs&viewer_version=2.11.1",
        },
        {
            "title": "Jupyterlab math v1.6.9",
            "file_type": "IPYNB",
            "view_url": f"{base_url}/view?file_type=IPYNB&viewer_key=simcore/services/dynamic/jupyter-octave-python-math&viewer_version=1.6.9",
        },
        {
            "title": "Bio-formats v1.0.1",
            "file_type": "JPEG",
            "view_url": f"{base_url}/view?file_type=JPEG&viewer_key=simcore/services/dynamic/bio-formats-web&viewer_version=1.0.1",
        },
        {
            "title": "Rawgraphs v2.11.1",
            "file_type": "JSON",
            "view_url": f"{base_url}/view?file_type=JSON&viewer_key=simcore/services/dynamic/raw-graphs&viewer_version=2.11.1",
        },
        {
            "title": "Bio-formats v1.0.1",
            "file_type": "PNG",
            "view_url": f"{base_url}/view?file_type=PNG&viewer_key=simcore/services/dynamic/bio-formats-web&viewer_version=1.0.1",
        },
        {
            "title": "Jupyterlab math v1.6.9",
            "file_type": "PY",
            "view_url": f"{base_url}/view?file_type=PY&viewer_key=simcore/services/dynamic/jupyter-octave-python-math&viewer_version=1.6.9",
        },
        {
            "title": "Rawgraphs v2.11.1",
            "file_type": "TSV",
            "view_url": f"{base_url}/view?file_type=TSV&viewer_key=simcore/services/dynamic/raw-graphs&viewer_version=2.11.1",
        },
        {
            "title": "Rawgraphs v2.11.1",
            "file_type": "XLSX",
            "view_url": f"{base_url}/view?file_type=XLSX&viewer_key=simcore/services/dynamic/raw-graphs&viewer_version=2.11.1",
        },
    ]


# REDIRECT ROUTES --------------------------------------------------------------------------------


@pytest.fixture
async def catalog_subsystem_mock(monkeypatch: MonkeyPatch) -> None:

    services_in_project = [
        {"key": "simcore/services/frontend/file-picker", "version": "1.0.0"}
    ] + [{"key": s.key, "version": s.version} for s in FAKE_VIEWS_LIST]

    async def mocked_get_services_for_user(*args, **kwargs):
        return services_in_project

    monkeypatch.setattr(
        catalog, "get_services_for_user_in_product", mocked_get_services_for_user
    )


@pytest.fixture
def mocks_on_projects_api(mocker):
    """
    All projects in this module are UNLOCKED
    """
    mocker.patch(
        "simcore_service_webserver.projects.projects_api._get_project_lock_state",
        return_value=ProjectLocked(value=False, status=ProjectStatus.CLOSED),
    )


async def assert_redirected_to_study(
    resp: ClientResponse, session: ClientSession
) -> str:
    content = await resp.text()
    assert resp.status == web.HTTPOk.status_code, f"Got {content}"

    # Expects redirection to osparc web
    assert resp.url.path == "/"
    assert (
        "OSPARC-SIMCORE" in content
    ), "Expected front-end rendering workbench's study, got %s" % str(content)

    # Expects auth cookie for current user
    assert "osparc.WEBAPI_SESSION" in [c.key for c in session.cookie_jar]

    # Expects fragment to indicate client where to find newly created project
    unquoted_fragment = urllib.parse.unquote_plus(resp.real_url.fragment)
    match = re.match(r"/view\?(.+)", unquoted_fragment)
    assert (
        match
    ), f"Expected fragment as /#/view?param1=value&param2=value, got {unquoted_fragment}"

    query_s = match.group(1)
    query_params = urllib.parse.parse_qs(
        query_s
    )  # returns {'param1': ['value'], 'param2': ['value']}

    assert "project_id" in query_params.keys()
    assert "viewer_node_id" in query_params.keys()

    assert all(len(query_params[key]) == 1 for key in query_params)

    # returns newly created project
    redirected_project_id = query_params["project_id"][0]
    return redirected_project_id


async def test_dispatch_viewer_anonymously(
    client,
    storage_subsystem_mock,
    catalog_subsystem_mock: None,
    mocks_on_projects_api,
    mocker,
):
    mock_client_director_v2_func = mocker.patch(
        "simcore_service_webserver.director_v2_api.create_or_update_pipeline",
        return_value=None,
    )

    redirect_url = (
        client.app.router["get_redirection_to_viewer"]
        .url_for()
        .with_query(
            file_name="users.csv",
            file_size=187,
            file_type="CSV",
            viewer_key="simcore/services/dynamic/raw-graphs",
            viewer_version="2.11.1",
            download_link=urllib.parse.quote(
                "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/8987c95d0ca0090e14f3a5b52db724fa24114cf5/services/storage/tests/data/users.csv"
            ),
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
    async def _get_user_projects():
        from servicelib.aiohttp.rest_responses import unwrap_envelope

        url = client.app.router["list_projects"].url_for()
        resp = await client.get(url.with_query(type="user"))

        payload = await resp.json()
        assert resp.status == 200, payload

        projects, error = unwrap_envelope(payload)
        assert not error, pprint(error)

        return projects

    projects = await _get_user_projects()
    assert len(projects) == 1
    guest_project = projects[0]

    assert expected_prj_id == guest_project["uuid"]
    assert guest_project["prjOwner"] == data["login"]

    assert mock_client_director_v2_func.called


def assert_error_in_fragment(resp: ClientResponse) -> tuple[str, int]:
    # Expects fragment to indicate client where to find newly created project
    unquoted_fragment = urllib.parse.unquote_plus(resp.real_url.fragment)
    match = re.match(r"/error\?(.+)", unquoted_fragment)
    assert match, f"Expected fragment as /#/view?message=..., got {unquoted_fragment}"

    query_s = match.group(1)
    # returns {'param1': ['value'], 'param2': ['value']}
    query_params = urllib.parse.parse_qs(query_s)

    assert {"message", "status_code"} == set(query_params.keys()), query_params
    assert all(len(query_params[key]) == 1 for key in query_params)

    message = query_params["message"][0]
    status_code = int(query_params["status_code"][0])
    return message, status_code


async def test_viewer_redirect_with_file_type_errors(client):
    redirect_url = (
        client.app.router["get_redirection_to_viewer"]
        .url_for()
        .with_query(
            file_name="users.csv",
            file_size=3 * 1024,
            file_type="INVALID_TYPE",  # <<<<<---------
            viewer_key="simcore/services/dynamic/raw-graphs",
            viewer_version="2.11.1",
            download_link=urllib.parse.quote(
                "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/8987c95d0ca0090e14f3a5b52db724fa24114cf5/services/storage/tests/data/users.csv"
            ),
        )
    )

    resp = await client.get(redirect_url)
    assert resp.status == 200

    message, status_code = assert_error_in_fragment(resp)

    assert status_code == web.HTTPUnprocessableEntity.status_code
    assert "type" in message.lower()


async def test_viewer_redirect_with_client_errors(client):
    redirect_url = (
        client.app.router["get_redirection_to_viewer"]
        .url_for()
        .with_query(
            file_name="users.csv",
            file_size=-1,  # <<<<<---------
            file_type="CSV",
            viewer_key="simcore/services/dynamic/raw-graphs",
            viewer_version="2.11.1",
            download_link=urllib.parse.quote("httnot a link"),  # <<<<<---------
        )
    )

    resp = await client.get(redirect_url)
    assert resp.status == 200

    message, status_code = assert_error_in_fragment(resp)
    print(message)
    assert status_code == web.HTTPBadRequest.status_code
