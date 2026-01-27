# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import re
import urllib.parse
from typing import Any
from unittest import mock

import pytest
from aiohttp import ClientResponse, ClientSession
from aiohttp.test_utils import TestClient, TestServer
from aioresponses import aioresponses
from common_library.json_serialization import json_dumps
from common_library.serialization import model_dump_with_secrets
from common_library.users_enums import UserRole
from models_library.projects_state import ProjectShareState, ProjectStatus
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME
from simcore_service_webserver.studies_dispatcher._models import ViewerInfo
from yarl import URL

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    rabbit_service: RabbitSettings,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {"WEBSERVER_RABBITMQ": json_dumps(model_dump_with_secrets(rabbit_service, show_secrets=True))},
    )


@pytest.fixture
def web_server(
    redis_service: RedisSettings,
    rabbit_service: RabbitSettings,
    web_server: TestServer,
    # Add dependencies to ensure database is populated before app starts
    services_metadata_in_db: list[dict],
    services_consume_filetypes_in_db: list[dict],
    services_access_rights_in_db: list[dict],
) -> TestServer:
    #
    # Extends web_server to start redis_service and ensure DB is populated
    #
    print("Redis service started with settings: ", redis_service.model_dump_json(indent=1))
    return web_server


@pytest.fixture(autouse=True)
async def director_v2_automock(
    director_v2_service_mock: aioresponses,
) -> aioresponses:
    return director_v2_service_mock


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


# REDIRECT ROUTES --------------------------------------------------------------------------------


@pytest.fixture
def catalog_subsystem_mock(mocker: MockerFixture) -> None:
    services_in_project = [{"key": "simcore/services/frontend/file-picker", "version": "1.0.0"}]
    services_in_project += [{"key": s.key, "version": s.version} for s in FAKE_VIEWS_LIST]

    mock = mocker.patch(
        "simcore_service_webserver.projects._crud_api_read.catalog_service.get_services_for_user_in_product",
        autospec=True,
    )

    async def _mocked_get_services_for_user(*args, **kwargs):
        return services_in_project

    mock.side_effect = _mocked_get_services_for_user


@pytest.fixture
def mocks_on_projects_api(mocker) -> None:
    """
    All projects in this module are UNLOCKED
    """
    mocker.patch(
        "simcore_service_webserver.projects._projects_service._get_project_share_state",
        return_value=ProjectShareState(locked=False, status=ProjectStatus.CLOSED, current_user_groupids=[]),
    )


async def assert_redirected_to_study(resp: ClientResponse, session: ClientSession) -> str:
    content = await resp.text()
    assert resp.status == status.HTTP_200_OK, f"Got {content}"

    # Expects redirection to osparc web
    assert resp.url.path == "/"
    assert "OSPARC-SIMCORE" in content, f"Expected front-end rendering workbench's study, got {content!s}"

    # Expects auth cookie for current user
    assert DEFAULT_SESSION_COOKIE_NAME in [c.key for c in session.cookie_jar]

    # Expects fragment to indicate client where to find newly created project
    unquoted_fragment = urllib.parse.unquote_plus(resp.real_url.fragment)
    match = re.match(r"/view\?(.+)", unquoted_fragment)
    assert match, f"Expected fragment as /#/view?param1=value&param2=value, got {unquoted_fragment}"

    query_s = match.group(1)
    query_params = urllib.parse.parse_qs(query_s)  # returns {'param1': ['value'], 'param2': ['value']}

    assert "project_id" in query_params
    assert "viewer_node_id" in query_params

    assert all(len(query_params[key]) == 1 for key in query_params)

    # returns newly created project
    return query_params["project_id"][0]


@pytest.fixture(params=["service_and_file", "service_only", "file_only"])
def redirect_type(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def redirect_url(redirect_type: str, client: TestClient) -> URL:
    assert client.app
    query: dict[str, Any] = {}
    if redirect_type == "service_and_file":
        query = {
            "file_name": "users.csv",
            "file_size": TypeAdapter(ByteSize).validate_python("100KB"),
            "file_type": "CSV",
            "viewer_key": "simcore/services/dynamic/raw-graphs",
            "viewer_version": "2.11.1",
            "download_link": URL(
                "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/8987c95d0ca0090e14f3a5b52db724fa24114cf5/services/storage/tests/data/users.csv"
            ),
        }
    elif redirect_type == "service_only":
        query = {
            "viewer_key": "simcore/services/dynamic/raw-graphs",
            "viewer_version": "2.11.1",
        }
    elif redirect_type == "file_only":
        query = {
            "file_name": "users.csv",
            "file_size": TypeAdapter(ByteSize).validate_python("1MiB"),
            "file_type": "CSV",
            "download_link": URL(
                "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/8987c95d0ca0090e14f3a5b52db724fa24114cf5/services/storage/tests/data/users.csv"
            ),
        }
    else:
        msg = f"{redirect_type=} undefined"
        raise ValueError(msg)

    return client.app.router["get_redirection_to_viewer"].url_for().with_query({k: f"{v}" for k, v in query.items()})


async def test_dispatch_study_anonymously(
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    redirect_url: URL,
    redirect_type: str,
    mocker: MockerFixture,
    storage_subsystem_mock,
    mocks_on_projects_api,
):
    assert client.app
    mock_client_director_v2_func = mocker.patch(
        "simcore_service_webserver.director_v2.director_v2_service.create_or_update_pipeline",
        return_value=None,
    )
    mock_dynamic_scheduler_update_project_networks = mocker.patch(
        "simcore_service_webserver.studies_dispatcher._controller.rest.redirects.dynamic_scheduler_service.update_projects_networks",
        return_value=None,
    )

    response = await client.get(f"{redirect_url}")

    if redirect_type == "file_only":
        message, status_code = assert_error_in_fragment(response)
        assert status_code == status.HTTP_401_UNAUTHORIZED, f"Got instead {status_code=}, {message=}"

    else:
        expected_project_id = await assert_redirected_to_study(response, client.session)

        # has auto logged in as guest?
        me_url = client.app.router["get_my_profile"].url_for()
        response = await client.get(f"{me_url}")

        data, _ = await assert_status(response, status.HTTP_200_OK)
        assert data["login"].endswith("guest-at-osparc.io")
        assert data["role"].upper() == UserRole.GUEST.name

        # guest user only a copy of the template project
        url = client.app.router["list_projects"].url_for()
        response = await client.get(f"{url.with_query(type='user')}")

        payload = await response.json()
        assert response.status == 200, payload

        projects, error = await assert_status(response, status.HTTP_200_OK)
        assert not error

        assert len(projects) == 1
        guest_project = projects[0]

        assert expected_project_id == guest_project["uuid"]
        assert guest_project["prjOwner"] == data["login"]

        assert mock_client_director_v2_func.called
        assert mock_dynamic_scheduler_update_project_networks.called


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.USER,
    ],
)
async def test_dispatch_logged_in_user(
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    redirect_url: URL,
    redirect_type: str,
    logged_user: UserInfoDict,
    mocker: MockerFixture,
    mock_dynamic_scheduler: None,
    storage_subsystem_mock,
    mocks_on_projects_api: None,
):
    assert client.app
    mock_client_director_v2_pipeline_update = mocker.patch(
        "simcore_service_webserver.director_v2.director_v2_service.create_or_update_pipeline",
        return_value=None,
    )
    mock_dynamic_scheduler_update_project_networks = mocker.patch(
        "simcore_service_webserver.studies_dispatcher._controller.rest.redirects.dynamic_scheduler_service.update_projects_networks",
        return_value=None,
    )

    response = await client.get(f"{redirect_url}")

    expected_project_id = await assert_redirected_to_study(response, client.session)

    # has auto logged in as guest?
    me_url = client.app.router["get_my_profile"].url_for()
    response = await client.get(f"{me_url}")

    data, _ = await assert_status(response, status.HTTP_200_OK)
    assert data["role"].upper() == UserRole.USER.name

    # guest user only a copy of the template project
    url = client.app.router["list_projects"].url_for()
    response = await client.get(f"{url.with_query(type='user')}")

    payload = await response.json()
    assert response.status == 200, payload

    projects, error = await assert_status(response, status.HTTP_200_OK)
    assert not error

    assert len(projects) == 1
    created_project = projects[0]

    assert expected_project_id == created_project["uuid"]
    assert created_project["prjOwner"] == data["login"]

    assert mock_client_director_v2_pipeline_update.called
    assert mock_dynamic_scheduler_update_project_networks.called

    # delete before exiting
    url = client.app.router["delete_project"].url_for(project_id=expected_project_id)
    response = await client.delete(f"{url}")
    await asyncio.sleep(2)  # needed to let task finish
    response.raise_for_status()


def assert_error_in_fragment(resp: ClientResponse) -> tuple[str, int]:
    # Expects fragment to indicate client where to find newly created project
    unquoted_fragment = urllib.parse.unquote_plus(resp.real_url.fragment)
    match = re.match(r"/error\?(.+)", unquoted_fragment, re.DOTALL)
    assert match, f"Expected error fragment as /#/error?message=..., got {unquoted_fragment}"

    query_s = match.group(1)
    # returns {'param1': ['value'], 'param2': ['value']}
    query_params = urllib.parse.parse_qs(query_s)

    assert {"message", "status_code"} == set(query_params.keys()), query_params
    assert all(len(query_params[key]) == 1 for key in query_params)

    message = query_params["message"][0]
    status_code = int(query_params["status_code"][0])
    return message, status_code


async def test_viewer_redirect_with_file_type_errors(client: TestClient):
    assert client.app
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

    resp = await client.get(f"{redirect_url}")
    assert resp.status == 200

    message, status_code = assert_error_in_fragment(resp)

    assert status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "link" in message.lower()


async def test_viewer_redirect_with_client_errors(client: TestClient):
    assert client.app
    redirect_url = (
        client.app.router["get_redirection_to_viewer"]
        .url_for()
        .with_query(
            file_name="users.csv",
            file_size=-1,  # <---------
            file_type="CSV",
            viewer_key="simcore/services/dynamic/raw-graphs",
            viewer_version="2.11.1",
            download_link="httnot a link",  # <---------
        )
    )

    # NOTE: that it validates against: ServiceAndFileParams | FileQueryParams | ServiceQueryParams
    # and the latter are strict i.e. Extra.forbid

    resp = await client.get(f"{redirect_url}")
    assert resp.status == 200

    message, status_code = assert_error_in_fragment(resp)
    print(message)
    assert status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.parametrize("missing_parameter", ["file_type", "file_size", "download_link"])
async def test_missing_file_param(client: TestClient, missing_parameter: str):
    assert client.app

    query = {
        "file_type": "CSV",
        "file_size": 1,
        "viewer_key": "simcore/services/dynamic/raw-graphs",
        "viewer_version": "2.11.1",
        "download_link": urllib.parse.quote(
            "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/8987c95d0ca0090e14f3a5b52db724fa24114cf5/services/storage/tests/data/users.csv"
        ),
    }
    query.pop(missing_parameter)

    redirect_url = client.app.router["get_redirection_to_viewer"].url_for().with_query(query)

    response = await client.get(f"{redirect_url}")
    assert response.status == 200

    message, status_code = assert_error_in_fragment(response)
    assert status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, f"Got {message=}"
