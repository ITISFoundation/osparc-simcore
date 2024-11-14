# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import re
import urllib.parse
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from copy import deepcopy
from pathlib import Path
from pprint import pformat

import pytest
import redis.asyncio as aioredis
from aiohttp import ClientResponse, ClientSession, web
from aiohttp.test_utils import TestClient, TestServer
from faker import Faker
from models_library.projects_state import ProjectLocked, ProjectStatus
from pytest_mock import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict, UserRole
from pytest_simcore.helpers.webserver_parametrizations import MockedStorageSubsystem
from pytest_simcore.helpers.webserver_projects import NewProject, delete_all_projects
from servicelib.aiohttp import status
from servicelib.aiohttp.long_running_tasks.client import LRTask
from servicelib.aiohttp.long_running_tasks.server import TaskProgress
from servicelib.aiohttp.rest_responses import unwrap_envelope
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.projects_api import submit_delete_project_task
from simcore_service_webserver.users.api import (
    delete_user_without_projects,
    get_user_role,
)
from tenacity import retry, stop_after_attempt, wait_fixed


async def _get_user_projects(client) -> list[ProjectDict]:
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(type="user"))

    payload = await resp.json()
    assert resp.status == status.HTTP_200_OK, payload

    projects, error = unwrap_envelope(payload)
    assert not error, pformat(error)

    return projects


def _assert_same_projects(got: dict, expected: dict):
    exclude = {
        "creationDate",
        "lastChangeDate",
        "prjOwner",
        "uuid",
        "workbench",
        "accessRights",
        "ui",
        "trashedExplicitly",
    }
    for key in expected:
        if key not in exclude:
            assert got[key] == expected[key], f"Failed in {key}"


def _is_user_authenticated(session: ClientSession) -> bool:
    return DEFAULT_SESSION_COOKIE_NAME in [c.key for c in session.cookie_jar]


@pytest.fixture
async def published_project(
    client: TestClient,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
    user: UserInfoDict,
) -> AsyncIterator[ProjectDict]:
    project_data = deepcopy(fake_project)
    project_data["name"] = "Published project"
    project_data["uuid"] = "e2e38eee-c569-4e55-b104-70d159e49c87"
    project_data["published"] = True  # PUBLIC
    project_data["access_rights"] = {
        # everyone HAS read access
        "1": {"read": True, "write": False, "delete": False}
    }
    async with NewProject(
        project_data,
        client.app,
        user_id=user["id"],
        as_template=True,  # <--IS a template
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
    ) as template_project:
        yield template_project


@pytest.fixture
async def unpublished_project(
    client: TestClient,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
    user: UserInfoDict,
) -> AsyncIterator[ProjectDict]:
    """An unpublished template"""

    project_data = deepcopy(fake_project)
    project_data["name"] = "Unpublished project"
    project_data["uuid"] = "b134a337-a74f-40ff-a127-b36a1ccbede6"
    project_data["published"] = False  # <--

    async with NewProject(
        project_data,
        client.app,
        user_id=user["id"],
        as_template=True,
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
    ) as template_project:
        yield template_project


@pytest.fixture
def mocks_on_projects_api(mocker: MockerFixture) -> None:
    """
    All projects in this module are UNLOCKED
    """
    mocker.patch(
        "simcore_service_webserver.projects.projects_api._get_project_lock_state",
        return_value=ProjectLocked(value=False, status=ProjectStatus.CLOSED),
    )


@pytest.fixture
async def storage_subsystem_mock_override(
    storage_subsystem_mock: MockedStorageSubsystem, mocker: MockerFixture
) -> None:
    """
    Mocks functions that require storage client

    NOTE: overrides conftest.storage_subsystem_mock
    """
    # Overrides + extends fixture in services/web/server/tests/unit/with_dbs/conftest.py
    # SEE https://docs.pytest.org/en/stable/fixture.html#override-a-fixture-on-a-folder-conftest-level

    # Mocks copy_data_folders_from_project BUT under studies_access
    mock = mocker.patch(
        "simcore_service_webserver.studies_dispatcher._studies_access.copy_data_folders_from_project",
        autospec=True,
    )

    async def _mock_copy_data_from_project(
        app, src_prj, dst_prj, nodes_map, user_id
    ) -> AsyncGenerator[LRTask, None]:
        print(
            f"MOCK copying data project {src_prj['uuid']} -> {dst_prj['uuid']} "
            f"with {len(nodes_map)} s3 objects by user={user_id}"
        )

        yield LRTask(TaskProgress(message="pytest mocked fct, started"))

        async def _mock_result():
            return None

        yield LRTask(
            TaskProgress(message="pytest mocked fct, finished", percent=1.0),
            _result=_mock_result(),
        )

    mock.side_effect = _mock_copy_data_from_project


def _assert_redirected_to_error_page(
    response: ClientResponse, expected_page: str, expected_status_code: int
):
    # checks is a redirection
    assert len(response.history) == 1
    assert response.history[0].status == 302

    # checks fragment
    fragment = response.history[0].headers["Location"]
    r = urllib.parse.urlparse(fragment.removeprefix("/#"))

    assert r.path == f"/{expected_page}"

    params = urllib.parse.parse_qs(r.query)
    assert params["status_code"] == [f"{expected_status_code}"], params


@retry(wait=wait_fixed(5), stop=stop_after_attempt(3))
async def _assert_redirected_to_study(
    response: ClientResponse, session: ClientSession
) -> str:
    # https://docs.aiohttp.org/en/stable/client_advanced.html#redirection-history
    assert len(response.history) == 1, "Is a re-direction"

    content = await response.text()
    assert response.status == status.HTTP_200_OK, f"Got {content}"

    # Expects redirection to osparc web
    assert response.url.path == "/"
    assert (
        "OSPARC-SIMCORE" in content
    ), "Expected front-end rendering workbench's study, got %s" % str(content)

    # Expects fragment to indicate client where to find newly created project
    m = re.match(r"/study/([\d\w-]+)", response.real_url.fragment)
    assert m, f"Expected /study/uuid, got {response.real_url.fragment}"

    # Expects auth cookie for current user
    assert _is_user_authenticated(session)

    # returns newly created project
    redirected_project_id = m.group(1)
    return redirected_project_id


# -----------------------------------------------------------
#
# Covers user stories for ISAN:
#
# - The ISAN Portal (M8; MS11.b,D11.b): https://github.com/ITISFoundation/osparc-simcore/issues/501
# - User access management for ISAN   : https://github.com/ITISFoundation/osparc-simcore/issues/712
# - Direct link to study in workbench : https://github.com/ITISFoundation/osparc-simcore/issues/730
#
# -----------------------------------------------------------


async def test_access_to_invalid_study(client: TestClient, faker: Faker):
    response = await client.get(f"/study/{faker.uuid4()}")

    _assert_redirected_to_error_page(
        response,
        expected_page="error",
        expected_status_code=status.HTTP_404_NOT_FOUND,
    )


async def test_access_to_forbidden_study(
    client: TestClient, unpublished_project: ProjectDict
):
    response = await client.get(f"/study/{unpublished_project['uuid']}")

    _assert_redirected_to_error_page(
        response,
        expected_page="error",
        expected_status_code=status.HTTP_401_UNAUTHORIZED,
    )


async def test_access_study_anonymously(
    client: TestClient,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    director_v2_service_mock: AioResponsesMock,
    mocks_on_projects_api: None,
    # needed to cleanup the locks between parametrizations
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    catalog_subsystem_mock([published_project])

    assert not _is_user_authenticated(client.session), "Is anonymous"
    assert client.app
    study_url = client.app.router["get_redirection_to_study_page"].url_for(
        id=published_project["uuid"]
    )

    resp = await client.get(f"{study_url}")

    expected_prj_id = await _assert_redirected_to_study(resp, client.session)

    # has auto logged in as guest?
    me_url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{me_url}")

    data, _ = await assert_status(resp, status.HTTP_200_OK)
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


@pytest.fixture
async def auto_delete_projects(client: TestClient) -> AsyncIterator[None]:
    assert client.app
    yield
    await delete_all_projects(client.app)


@pytest.mark.parametrize("user_role", [UserRole.USER, UserRole.TESTER])
async def test_access_study_by_logged_user(
    client: TestClient,
    logged_user: UserInfoDict,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    director_v2_service_mock: AioResponsesMock,
    mocks_on_projects_api: None,
    auto_delete_projects: None,
    # needed to cleanup the locks between parametrizations
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    assert client.app
    catalog_subsystem_mock([published_project])
    assert _is_user_authenticated(client.session), "Is already logged-in"

    study_url = client.app.router["get_redirection_to_study_page"].url_for(
        id=published_project["uuid"]
    )
    resp = await client.get(f"{study_url}")
    await _assert_redirected_to_study(resp, client.session)

    # user has a copy of the template project
    projects = await _get_user_projects(client)
    assert len(projects) == 1
    user_project = projects[0]

    # heck redirects to /#/study/{uuid}
    assert resp.real_url.fragment.endswith("/study/%s" % user_project["uuid"])
    _assert_same_projects(user_project, published_project)

    assert user_project["prjOwner"] == logged_user["email"]


async def test_access_cookie_of_expired_user(
    client: TestClient,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    director_v2_service_mock: AioResponsesMock,
    mock_dynamic_scheduler: None,
    mocks_on_projects_api: None,
    # needed to cleanup the locks between parametrizations
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    catalog_subsystem_mock([published_project])
    # emulates issue #1570
    assert client.app  # nosec
    app: web.Application = client.app

    study_url = app.router["get_redirection_to_study_page"].url_for(
        id=published_project["uuid"]
    )
    resp = await client.get(f"{study_url}")

    await _assert_redirected_to_study(resp, client.session)

    # Expects valid cookie and GUEST access
    me_url = app.router["get_my_profile"].url_for()
    resp = await client.get(f"{me_url}")

    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert await get_user_role(app, data["id"]) == UserRole.GUEST

    async def enforce_garbage_collect_guest(uid):
        # TODO: can be replaced now by actual GC
        # Emulates garbage collector:
        #   - GUEST user expired, cleaning it up
        #   - client still holds cookie with its identifier nonetheless
        #
        assert await get_user_role(app, uid) == UserRole.GUEST
        projects = await _get_user_projects(client)
        assert len(projects) == 1

        prj_id = projects[0]["uuid"]

        delete_task = await submit_delete_project_task(
            app, prj_id, uid, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
        )
        await delete_task

        await delete_user_without_projects(app, uid)
        return uid

    user_id = await enforce_garbage_collect_guest(uid=data["id"])
    user_email = data["login"]

    # Now this should be non -authorized
    resp = await client.get(f"{me_url}")
    await assert_status(resp, status.HTTP_401_UNAUTHORIZED)

    # But still can access as a new user
    resp = await client.get(f"{study_url}")
    await _assert_redirected_to_study(resp, client.session)

    # as a guest user
    resp = await client.get(f"{me_url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert await get_user_role(app, data["id"]) == UserRole.GUEST

    # But I am another user
    assert data["id"] != user_id
    assert data["login"] != user_email


@pytest.mark.parametrize("number_of_simultaneous_requests", [1, 2, 64])
async def test_guest_user_is_not_garbage_collected(
    number_of_simultaneous_requests: int,
    web_server: TestServer,
    aiohttp_client: Callable,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    director_v2_service_mock: AioResponsesMock,
    mocks_on_projects_api: None,
    # needed to cleanup the locks between parametrizations
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    catalog_subsystem_mock([published_project])
    ## NOTE: use pytest -s --log-cli-level=DEBUG  to see GC logs

    async def _test_guest_user_workflow(request_index):
        print("request #", request_index, "-" * 10)

        # TODO: heartbeat is missing here!
        # TODO: reduce GC activation period to 0.1 secs
        # every guest uses different client to preserve it's own authorization/authentication cookies
        client: TestClient = await aiohttp_client(web_server)
        assert client.app
        study_url = client.app.router["get_redirection_to_study_page"].url_for(
            id=published_project["uuid"]
        )

        # clicks link to study
        resp = await client.get(f"{study_url}")

        expected_prj_id = await _assert_redirected_to_study(resp, client.session)

        # has auto logged in as guest?
        me_url = client.app.router["get_my_profile"].url_for()
        resp = await client.get(f"{me_url}")

        data, _ = await assert_status(resp, status.HTTP_200_OK)
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
        print("request #", request_index, "DONE", "-" * 10)

    # N concurrent requests
    request_tasks = [
        asyncio.create_task(_test_guest_user_workflow(n))
        for n in range(number_of_simultaneous_requests)
    ]

    await asyncio.gather(*request_tasks)

    # and now the garbage collector shall delete our users since we are done...
