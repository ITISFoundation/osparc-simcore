# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import urllib.parse
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from copy import deepcopy
from pathlib import Path
from pprint import pformat
from typing import Any
from unittest import mock

import pytest
import redis.asyncio as aioredis
from aiohttp import ClientResponse, ClientSession, web
from aiohttp.test_utils import TestClient, TestServer
from celery_library.async_jobs import (
    AsyncJobResultUpdate,
)
from common_library.users_enums import UserRole
from faker import Faker
from models_library.api_schemas_async_jobs.async_jobs import AsyncJobStatus
from models_library.progress_bar import ProgressReport
from models_library.projects_state import (
    ProjectShareState,
    ProjectStatus,
)
from models_library.users import UserID
from pytest_mock import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_parametrizations import MockedStorageSubsystem
from pytest_simcore.helpers.webserver_projects import NewProject, delete_all_projects
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rest_responses import unwrap_envelope
from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME
from simcore_service_webserver.projects import projects_trash_service
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.utils import NodesMap
from simcore_service_webserver.trash import trash_service
from simcore_service_webserver.users.users_service import (
    delete_user_without_projects,
    get_user_role,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]


async def _get_user_projects(client) -> list[ProjectDict]:
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(type="user"))

    payload = await resp.json()
    assert resp.status == status.HTTP_200_OK, payload

    projects, error = unwrap_envelope(payload)
    assert not error, pformat(error)

    return projects


def _assert_same_projects(got: dict[str, Any], expected: dict[str, Any]):
    exclude = {
        "accessRights",
        "creationDate",
        "lastChangeDate",
        "prjOwner",
        "trashedAt",
        "trashedBy",
        "trashedExplicitly",
        "ui",
        "uuid",
        "workbench",
        "type",
        "templateType",
        "productName",
    }
    expected_values = {k: v for k, v in expected.items() if k not in exclude}
    got_values = {k: got[k] for k in expected if k not in exclude}

    assert got_values == expected_values


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
    import simcore_service_webserver.projects._projects_service  # noqa: PLC0415

    mocker.patch.object(
        simcore_service_webserver.projects._projects_service,  # noqa: SLF001
        "_get_project_share_state",
        return_value=ProjectShareState(locked=False, status=ProjectStatus.CLOSED, current_user_groupids=[]),
    )


@pytest.fixture
async def storage_subsystem_mock_override(
    storage_subsystem_mock: MockedStorageSubsystem, mocker: MockerFixture, faker: Faker
) -> None:
    """
    Mocks functions that require storage client

    NOTE: overrides conftest.storage_subsystem_mock
    """
    # Overrides + extends fixture in services/web/server/tests/unit/with_dbs/conftest.py
    # SEE https://docs.pytest.org/en/stable/fixture.html#override-a-fixture-on-a-folder-conftest-level

    # Mocks copy_data_folders_from_project used by the shared clone_project_data primitive
    mock = mocker.patch(
        "simcore_service_webserver.projects._projects_service.storage_service.copy_data_folders_from_project",
        autospec=True,
    )

    async def _mock_copy_data_from_project(
        app: web.Application,
        *,
        source_project: ProjectDict,
        destination_project: ProjectDict,
        nodes_map: NodesMap,
        user_id: UserID,
        product_name: str,
    ) -> AsyncGenerator[AsyncJobResultUpdate]:
        print(
            f"MOCK copying data project {source_project['uuid']} -> {destination_project['uuid']} "
            f"with {len(nodes_map)} s3 objects by user={user_id}"
        )

        yield AsyncJobResultUpdate(
            AsyncJobStatus(
                job_id=faker.uuid4(cast_to=None),
                progress=ProgressReport(actual_value=0),
                done=False,
            )
        )

        async def _mock_result():
            return None

        yield AsyncJobResultUpdate(
            AsyncJobStatus(
                job_id=faker.uuid4(cast_to=None),
                progress=ProgressReport(actual_value=1),
                done=True,
            ),
            _mock_result(),
        )

    mock.side_effect = _mock_copy_data_from_project


def _assert_redirected_to_error_page(response: ClientResponse, expected_page: str, expected_status_code: int):
    # checks is a redirection
    assert len(response.history) == 1
    assert response.history[0].status == 302

    # checks fragment
    fragment = response.history[0].headers["Location"]
    r = urllib.parse.urlparse(fragment.removeprefix("/#"))

    assert r.path == f"/{expected_page}"

    params = urllib.parse.parse_qs(r.query)
    assert params["status_code"] == [f"{expected_status_code}"], params


def _assert_dispatch_redirect(response: ClientResponse, source_study_id: str) -> None:
    """Assert GET /study/{id} responded with an immediate 302 to the SPA dispatch fragment.

    In the new split-flow the server redirects immediately (no clone yet) to
    ``/#/dispatch?study_id={source_study_id}``.  The actual clone is triggered
    separately by the SPA via POST /{VTAG}/studies/{id}:dispatch.
    """
    assert len(response.history) == 1, "Expected exactly 1 redirect from GET /study/{id}"
    assert response.status == status.HTTP_200_OK, f"Expected 200 after redirect, got {response.status}"
    assert response.url.path == "/", "Expected redirect to root SPA page"
    fragment = response.real_url.fragment
    assert fragment == f"/dispatch?study_id={source_study_id}", (
        f"Expected fragment '/dispatch?study_id={source_study_id}', got {fragment!r}"
    )


async def _dispatch_and_poll(client: TestClient, study_id: str, *, max_iters: int = 60) -> str:
    """POST :dispatch and poll until completion. Returns the cloned project UUID."""
    assert client.app
    dispatch_url = str(client.app.router["dispatch_study"].url_for(study_id=study_id))
    resp = await client.post(dispatch_url)
    payload = await resp.json()
    assert resp.status == status.HTTP_202_ACCEPTED, f"Expected 202 from :dispatch, got {resp.status}: {payload}"

    task_data = payload.get("data") or payload
    status_href: str = task_data["status_href"]
    result_href: str = task_data["result_href"]

    for _ in range(max_iters):
        await asyncio.sleep(0.1)
        poll_resp = await client.get(urllib.parse.urlparse(status_href).path)
        poll_payload = await poll_resp.json()
        assert poll_resp.status == status.HTTP_200_OK, f"Task status poll failed: {poll_payload}"
        task_status = poll_payload.get("data") or poll_payload
        if task_status.get("done"):
            result_resp = await client.get(urllib.parse.urlparse(result_href).path)
            result_payload = await result_resp.json()
            assert result_resp.status == status.HTTP_200_OK, f"Task result failed: {result_payload}"
            result = result_payload.get("data") or result_payload
            project_id: str | None = result.get("project_id")
            assert project_id, f"Expected project_id in task result, got: {result}"
            return project_id

    pytest.fail(f"Dispatch task for study {study_id!r} did not complete in {max_iters * 0.1:.1f}s")


# -----------------------------------------------------------
#
# Covers user stories for ISAN:
#
# - The ISAN Portal (M8; MS11.b,D11.b): https://github.com/ITISFoundation/osparc-simcore/issues/501
# - User access management for ISAN   : https://github.com/ITISFoundation/osparc-simcore/issues/712
# - Direct link to study in workbench : https://github.com/ITISFoundation/osparc-simcore/issues/730
#
# -----------------------------------------------------------


async def test_access_to_invalid_study(
    studies_dispatcher_enabled: bool,
    client: TestClient,
    faker: Faker,
):
    invalid_project_id = faker.uuid4()
    response = await client.get(f"/study/{invalid_project_id}")

    _assert_redirected_to_error_page(
        response,
        expected_page="error",
        expected_status_code=status.HTTP_404_NOT_FOUND,
    )


async def test_access_to_forbidden_study(
    studies_dispatcher_enabled: bool,
    client: TestClient,
    unpublished_project: ProjectDict,
):
    response = await client.get(f"/study/{unpublished_project['uuid']}")

    _assert_redirected_to_error_page(
        response,
        expected_page="error",
        expected_status_code=status.HTTP_401_UNAUTHORIZED,
    )


async def test_access_study_anonymously(
    studies_dispatcher_enabled: bool,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    mock_dynamic_scheduler: None,
    director_v2_service_mock: AioResponsesMock,
    mocks_on_projects_api: None,
    # needed to cleanup the locks between parametrizations
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    assert not _is_user_authenticated(client.session), "Is anonymous"
    assert client.app
    study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])

    resp = await client.get(f"{study_url}")

    # New split-flow: GET redirects immediately to dispatch fragment, no clone yet
    _assert_dispatch_redirect(resp, published_project["uuid"])
    assert _is_user_authenticated(client.session), "Guest session must be set before the clone"

    # SPA now calls :dispatch to start the clone task, then polls to completion
    expected_prj_id = await _dispatch_and_poll(client, published_project["uuid"])

    # has auto logged in as guest?
    me_url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{me_url}")

    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["login"].endswith("guest-at-osparc.io")
    assert data["role"].upper() == UserRole.GUEST.name

    # guest user only a copy of the template project
    projects = await _get_user_projects(client)
    assert len(projects) == 1
    guest_project = projects[0]

    assert expected_prj_id == guest_project["uuid"]
    _assert_same_projects(guest_project, published_project)

    assert guest_project["prjOwner"] == data["login"]


async def test_access_study_anonymously_with_trailing_slash(
    studies_dispatcher_enabled: bool,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    mock_dynamic_scheduler: None,
    director_v2_service_mock: AioResponsesMock,
    mocks_on_projects_api: None,
    # needed to cleanup the locks between parametrizations
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    assert not _is_user_authenticated(client.session), "Is anonymous"
    assert client.app
    study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])

    # a trailing slash must be dispatched to the same handler (e.g. '/study/{id}/')
    resp = await client.get(f"{study_url}/")

    # New split-flow: GET redirects immediately to dispatch fragment, no clone yet
    _assert_dispatch_redirect(resp, published_project["uuid"])
    assert _is_user_authenticated(client.session), "Guest session must be set before the clone"


@pytest.fixture
async def auto_delete_projects(client: TestClient) -> AsyncIterator[None]:
    assert client.app
    yield
    await delete_all_projects(client.app)


@pytest.mark.parametrize("user_role", [UserRole.USER, UserRole.TESTER])
async def test_access_study_by_logged_user(
    studies_dispatcher_enabled: bool,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    mock_dynamic_scheduler: None,
    director_v2_service_mock: AioResponsesMock,
    mocks_on_projects_api: None,
    auto_delete_projects: None,
    # needed to cleanup the locks between parametrizations
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    assert client.app
    assert _is_user_authenticated(client.session), "Is already logged-in"

    study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])
    resp = await client.get(f"{study_url}")

    # New split-flow: GET redirects immediately to dispatch fragment, no clone yet
    _assert_dispatch_redirect(resp, published_project["uuid"])

    # SPA now calls :dispatch to start the clone task, then polls to completion
    cloned_project_id = await _dispatch_and_poll(client, published_project["uuid"])

    # user has a copy of the template project
    projects = await _get_user_projects(client)
    assert len(projects) == 1
    user_project = projects[0]

    assert user_project["uuid"] == cloned_project_id
    _assert_same_projects(user_project, published_project)

    assert user_project["prjOwner"] == logged_user["email"]


async def test_access_cookie_of_expired_user(
    studies_dispatcher_enabled: bool,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    director_v2_service_mock: AioResponsesMock,
    mock_dynamic_scheduler: None,
    mocks_on_projects_api: None,
    # needed to cleanup the locks between parametrizations
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    # emulates issue #1570
    assert client.app  # nosec
    app: web.Application = client.app

    study_url = app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])
    resp = await client.get(f"{study_url}")

    # New split-flow: GET redirects immediately to dispatch fragment, no clone yet
    _assert_dispatch_redirect(resp, published_project["uuid"])
    assert _is_user_authenticated(client.session), "Guest session must be set"

    # SPA calls :dispatch to start the clone task, then polls to completion
    await _dispatch_and_poll(client, published_project["uuid"])

    # Expects valid cookie and GUEST access
    me_url = app.router["get_my_profile"].url_for()
    resp = await client.get(f"{me_url}")

    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert await get_user_role(app, user_id=data["id"]) == UserRole.GUEST

    async def enforce_garbage_collect_guest(uid):
        # TODO: can be replaced now by actual GC  # noqa: FIX002
        # Emulates garbage collector:
        #   - GUEST user expired, cleaning it up
        #   - client still holds cookie with its identifier nonetheless
        #
        assert await get_user_role(app, user_id=uid) == UserRole.GUEST
        projects = await _get_user_projects(client)
        assert len(projects) == 1

        prj_id = projects[0]["uuid"]

        await projects_trash_service.mark_for_immediate_deletion(
            app, product_name="osparc", user_id=uid, project_id=prj_id
        )
        # NOTE: actual removal now happens exclusively via the periodic trash-pruning GC
        await trash_service.safe_delete_expired_trash_as_admin(app)

        await delete_user_without_projects(app, user_id=uid)
        return uid

    user_id = await enforce_garbage_collect_guest(uid=data["id"])
    user_email = data["login"]

    # Now this should be non -authorized
    resp = await client.get(f"{me_url}")
    await assert_status(resp, status.HTTP_401_UNAUTHORIZED)

    # But still can access as a new user
    resp = await client.get(f"{study_url}")
    # New split-flow: the GET sets a new guest session and redirects to the dispatch fragment
    _assert_dispatch_redirect(resp, published_project["uuid"])
    assert _is_user_authenticated(client.session), "New guest session must be set"

    # as a guest user
    resp = await client.get(f"{me_url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert await get_user_role(app, user_id=data["id"]) == UserRole.GUEST

    # But I am another user
    assert data["id"] != user_id
    assert data["login"] != user_email


@pytest.mark.flaky(max_runs=3)
@pytest.mark.parametrize(
    "number_of_simultaneous_requests",
    [
        1,
        2,
        16,
        # NOTE: The number of simultaneous anonymous users is limited by system load.
        # A GuestUsersLimitError is raised if user creation exceeds the MAX_DELAY_TO_CREATE_USER threshold.
        # This test is flaky due to its dependency on app runtime conditions. Avoid increasing simultaneous requests.
    ],
)
async def test_guest_user_is_not_garbage_collected(
    studies_dispatcher_enabled: bool,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    number_of_simultaneous_requests: int,
    web_server: TestServer,
    aiohttp_client: Callable,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    mock_dynamic_scheduler: None,
    director_v2_service_mock: AioResponsesMock,
    mocks_on_projects_api: None,
    # needed to cleanup the locks between parametrizations
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    ## NOTE: use pytest -s --log-cli-level=DEBUG  to see GC logs

    async def _test_guest_user_workflow(request_index):
        print("request #", request_index, "-" * 10)
        # every guest uses different client to preserve it's own authorization/authentication cookies
        client: TestClient = await aiohttp_client(web_server)
        assert client.app
        study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])

        # clicks link to study
        resp = await client.get(f"{study_url}")

        # New split-flow: GET redirects immediately, sets guest session
        _assert_dispatch_redirect(resp, published_project["uuid"])
        assert _is_user_authenticated(client.session), "Guest session must be set"

        # SPA calls :dispatch to start the clone task, then polls to completion
        expected_prj_id = await _dispatch_and_poll(client, published_project["uuid"])

        # has auto logged in as guest?
        me_url = client.app.router["get_my_profile"].url_for()
        resp = await client.get(f"{me_url}")

        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert data["login"].endswith("guest-at-osparc.io")
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
    request_tasks = [asyncio.create_task(_test_guest_user_workflow(n)) for n in range(number_of_simultaneous_requests)]

    await asyncio.gather(*request_tasks)
    # and now the garbage collector shall delete our users since we are done...


@pytest.mark.parametrize("studies_dispatcher_enabled", [False], indirect=True)
async def test_access_study_with_dispatcher_disabled(
    studies_dispatcher_enabled: bool,
    client: TestClient,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
):
    """
    Test that accessing /study redirects to the SPA error page when studies_dispatcher_enabled is False.

    When the product has studies_dispatcher_enabled=False, the dispatcher feature
    should be completely disabled, and accessing the /study endpoint should result
    in a redirect to the front-end error page — never a raw HTTP response.
    """
    assert not _is_user_authenticated(client.session), "Is anonymous"
    assert client.app

    study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])
    resp = await client.get(f"{study_url}")

    _assert_redirected_to_error_page(
        resp,
        expected_page="error",
        expected_status_code=status.HTTP_404_NOT_FOUND,
    )

    # User should NOT be auto-logged in as guest when dispatcher is disabled
    me_url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{me_url}")
    assert resp.status == status.HTTP_401_UNAUTHORIZED, "Dispatcher disabled, so guest login should not have occurred"


@pytest.mark.parametrize("user_role", [UserRole.USER, UserRole.TESTER])
@pytest.mark.parametrize("studies_dispatcher_enabled", [False], indirect=True)
async def test_access_study_by_logged_user_with_dispatcher_disabled(
    studies_dispatcher_enabled: bool,
    client: TestClient,
    logged_user: UserInfoDict,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    user_role: UserRole,
):
    """
    Test that accessing /study redirects to the SPA error page for logged-in users
    when studies_dispatcher_enabled is False.

    Even logged-in users should not be able to access the dispatcher
    when the feature is disabled at the product level.
    """
    assert _is_user_authenticated(client.session), "Is already logged-in"
    assert client.app

    study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])
    resp = await client.get(f"{study_url}")

    _assert_redirected_to_error_page(
        resp,
        expected_page="error",
        expected_status_code=status.HTTP_404_NOT_FOUND,
    )


@pytest.mark.parametrize("studies_dispatcher_enabled", [True], indirect=True)
async def test_access_study_anonymously_with_login_required(
    studies_dispatcher_enabled: bool,
    client: TestClient,
    published_project: ProjectDict,
    mocker: MockerFixture,
):
    """
    When STUDIES_ACCESS_ANONYMOUS_ALLOWED=0 (login required) and an anonymous user
    accesses /study/{id}, the handler must redirect to the SPA error page with
    status_code=401 — never return a raw HTTP response.
    """
    mock_settings = mocker.MagicMock()
    mock_settings.is_login_required.return_value = True
    mocker.patch(
        "simcore_service_webserver.studies_dispatcher._studies_access.get_plugin_settings",
        return_value=mock_settings,
    )

    assert not _is_user_authenticated(client.session), "Is anonymous"
    assert client.app

    study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])
    resp = await client.get(f"{study_url}")

    _assert_redirected_to_error_page(
        resp,
        expected_page="error",
        expected_status_code=status.HTTP_401_UNAUTHORIZED,
    )

    # User must NOT have been auto-logged in as guest
    me_url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{me_url}")
    assert resp.status == status.HTTP_401_UNAUTHORIZED
