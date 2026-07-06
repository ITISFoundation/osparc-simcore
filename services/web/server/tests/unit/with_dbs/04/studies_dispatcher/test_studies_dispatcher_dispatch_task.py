# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Acceptance tests for the split redirect + polled clone workflow.

New workflow (fixes 2+4 hybrid):
  1. GET /study/{id}  → fast 302 to SPA dispatching fragment; guest session set; no clone yet.
  2. POST /{VTAG}/studies/{id}:dispatch  → 202 + TaskGet  (GUEST-accessible; study.dispatch perm)
  3. Poll status_href  → done; GET result_href  → contains cloned project_id.

These tests are the completion gate (Phase 0): implementation is done when this suite passes.
"""

import re
import urllib.parse
from collections.abc import AsyncIterator
from copy import deepcopy
from pathlib import Path
from pprint import pformat
from unittest import mock

import pytest
import redis.asyncio as aioredis
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestClient
from celery_library.async_jobs import AsyncJobResultUpdate
from common_library.users_enums import UserRole
from faker import Faker
from models_library.api_schemas_async_jobs.async_jobs import AsyncJobStatus
from models_library.progress_bar import ProgressReport
from models_library.projects_state import ProjectShareState, ProjectStatus
from models_library.users import UserID
from pytest_mock import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.webserver_parametrizations import MockedStorageSubsystem
from pytest_simcore.helpers.webserver_projects import NewProject
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rest_responses import unwrap_envelope
from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.utils import NodesMap
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_user_authenticated(session: ClientSession) -> bool:
    return DEFAULT_SESSION_COOKIE_NAME in [c.key for c in session.cookie_jar]


async def _get_user_projects(client: TestClient) -> list[ProjectDict]:
    assert client.app
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(type="user"))
    payload = await resp.json()
    assert resp.status == status.HTTP_200_OK, payload
    projects, error = unwrap_envelope(payload)
    assert not error, pformat(error)
    return projects


def _dispatch_url(client: TestClient, study_id: str) -> str:
    """Returns the URL for the new dispatch endpoint."""
    assert client.app
    # New route: POST /{VTAG}/studies/{study_id}:dispatch
    return str(client.app.router["dispatch_study"].url_for(study_id=study_id))


def _assert_dispatch_fragment(fragment: str) -> str:
    """Assert fragment is the SPA dispatching route and return the study_id."""
    # Expected: /#/dispatch?study_id={study_id}
    m = re.match(r"(?:/dispatch\?study_id=|/study/)([0-9a-f\-]+)(?:/dispatch)?$", fragment)
    assert m, f"Expected fragment with dispatch route, got: {fragment!r}"
    return m.group(1)


async def _poll_lr_task_until_done(client: TestClient, status_href: str) -> None:
    """Poll the LRT status endpoint until done, retrying via tenacity instead of a fixed sleep loop."""
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            poll_resp = await client.get(urllib.parse.urlparse(status_href).path)
            poll_payload = await poll_resp.json()
            assert poll_resp.status == status.HTTP_200_OK, poll_payload
            task_status = poll_payload.get("data") or poll_payload
            assert task_status.get("done"), "task incomplete"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def published_project(
    client: TestClient,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
    user: UserInfoDict,
) -> AsyncIterator[ProjectDict]:
    project_data = deepcopy(fake_project)
    project_data["name"] = "Published dispatch project"
    project_data["uuid"] = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    project_data["published"] = True
    project_data["access_rights"] = {
        "1": {"read": True, "write": False, "delete": False}  # everyone
    }
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
async def unpublished_project(
    client: TestClient,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
    user: UserInfoDict,
) -> AsyncIterator[ProjectDict]:
    project_data = deepcopy(fake_project)
    project_data["name"] = "Unpublished dispatch project"
    project_data["uuid"] = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
    project_data["published"] = False
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
    """Mocks copy_data_folders_from_project used by the dispatch task."""
    mock_fn = mocker.patch(
        "simcore_service_webserver.studies_dispatcher._dispatch_task.copy_data_folders_from_project",
        autospec=True,
    )

    async def _mock_copy(
        app: web.Application,
        *,
        source_project: ProjectDict,
        destination_project: ProjectDict,
        nodes_map: NodesMap,
        user_id: UserID,
        product_name: str,
    ):
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

    mock_fn.side_effect = _mock_copy


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


# Phase 0 — Test A: GET /study/{id} redirects immediately, sets guest cookie, no clone yet
async def test_study_link_redirects_immediately_to_dispatch_fragment(
    studies_dispatcher_enabled: bool,
    client: TestClient,
    published_project: ProjectDict,
):
    """
    GET /study/{id} must:
    - return a 302 redirect immediately (before any cloning happens)
    - set a guest session cookie if user was anonymous
    - redirect to a SPA 'dispatching' route fragment (not the final study route)
    - NOT have created any project copy yet
    """
    assert client.app
    assert not _is_user_authenticated(client.session), "Precondition: user is anonymous"

    study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])
    resp = await client.get(f"{study_url}", allow_redirects=False)

    # Must be an immediate redirect, not waiting for clone
    assert resp.status == status.HTTP_302_FOUND, f"Expected 302, got {resp.status}"

    # Guest session cookie must already be set (remember_identity happened)
    assert _is_user_authenticated(client.session), "Guest session must be set before the clone"

    # Fragment must point to a 'dispatching' route, NOT to /#/study/{cloned_id}
    location = resp.headers["Location"]
    fragment = urllib.parse.urlparse(location).fragment
    source_id = _assert_dispatch_fragment(fragment)
    assert source_id == published_project["uuid"], "Dispatch fragment must carry the source study id"

    # No copy must exist yet
    projects = await _get_user_projects(client)
    assert projects == [], f"No project copy should exist yet, got: {projects}"


# Phase 0 — Test B: POST dispatch endpoint returns 202 + TaskGet for authenticated guest
async def test_dispatch_endpoint_starts_task_for_guest(
    studies_dispatcher_enabled: bool,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    mock_dynamic_scheduler: None,
    director_v2_service_mock: AioResponsesMock,
    mocks_on_projects_api: None,
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    """
    After the guest session is set via GET /study/{id},
    POST /{VTAG}/studies/{study_id}:dispatch must return 202 + TaskGet.
    """
    assert client.app

    # Step 1: get fast redirect to establish guest session
    study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])
    await client.get(f"{study_url}")
    assert _is_user_authenticated(client.session), "Guest must be authenticated after redirect"

    # Step 2: call dispatch endpoint
    dispatch_url = _dispatch_url(client, published_project["uuid"])
    resp = await client.post(dispatch_url)
    payload = await resp.json()

    assert resp.status == status.HTTP_202_ACCEPTED, f"Expected 202, got {resp.status}: {payload}"
    data = payload.get("data") or payload
    assert "task_id" in data, f"Expected task_id in response, got: {data}"
    assert "status_href" in data, f"Expected status_href in response, got: {data}"
    assert "result_href" in data, f"Expected result_href in response, got: {data}"
    assert "abort_href" in data, f"Expected abort_href in response, got: {data}"


# Phase 0 — Test C: Polling the task until done returns the cloned project_id
async def test_dispatch_task_completes_and_returns_cloned_project_id(
    studies_dispatcher_enabled: bool,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    mock_dynamic_scheduler: None,
    director_v2_service_mock: AioResponsesMock,
    mocks_on_projects_api: None,
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    """
    Full happy-path: anonymous user follows the redirect, calls dispatch, polls to done.
    After completion:
    - result_href contains the cloned project_id
    - guest owns exactly one project that is a copy of the template
    """
    assert client.app

    # Establish guest session
    study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])
    await client.get(f"{study_url}")
    assert _is_user_authenticated(client.session)

    # Start clone task (emulates SPA operation)
    dispatch_url = _dispatch_url(client, published_project["uuid"])
    resp = await client.post(dispatch_url)
    assert resp.status == status.HTTP_202_ACCEPTED
    task_data = (await resp.json()).get("data") or (await resp.json())
    status_href: str = task_data["status_href"]
    result_href: str = task_data["result_href"]

    # Poll until done (task is backed by the LRT machinery)
    await _poll_lr_task_until_done(client, status_href)

    # Fetch result
    result_resp = await client.get(urllib.parse.urlparse(result_href).path)
    result_payload = await result_resp.json()
    assert result_resp.status == status.HTTP_200_OK, result_payload
    result = result_payload.get("data") or result_payload
    cloned_project_id = result.get("project_id")
    assert cloned_project_id, f"Expected project_id in task result, got: {result}"

    # Guest owns exactly one project that is a copy of the template
    projects = await _get_user_projects(client)
    assert len(projects) == 1, f"Guest should own exactly one project, got: {projects}"
    assert projects[0]["uuid"] == cloned_project_id


# Phase 0 — Test D: Already-logged-in USER also works (no guest created)
@pytest.mark.parametrize("user_role", [UserRole.USER, UserRole.TESTER])
async def test_dispatch_works_for_logged_user(
    studies_dispatcher_enabled: bool,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    published_project: ProjectDict,
    storage_subsystem_mock_override: None,
    mock_dynamic_scheduler: None,
    director_v2_service_mock: AioResponsesMock,
    mocks_on_projects_api: None,
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    assert client.app
    assert _is_user_authenticated(client.session), "Must be logged in"

    # Start task directly (no need for GET /study first for logged-in users)
    dispatch_url = _dispatch_url(client, published_project["uuid"])
    resp = await client.post(dispatch_url)
    assert resp.status == status.HTTP_202_ACCEPTED, await resp.text()
    task_data = (await resp.json()).get("data") or (await resp.json())
    status_href = task_data["status_href"]
    result_href = task_data["result_href"]

    # Poll until done (emulates SPA operation)
    await _poll_lr_task_until_done(client, status_href)

    result_resp = await client.get(urllib.parse.urlparse(result_href).path)
    result = (await result_resp.json()).get("data") or (await result_resp.json())
    assert result.get("project_id"), f"Expected project_id, got: {result}"


# Phase 0 — Security Test 1: GUEST cannot dispatch a non-published project
async def test_guest_cannot_dispatch_unpublished_project(
    studies_dispatcher_enabled: bool,
    client: TestClient,
    published_project: ProjectDict,
    unpublished_project: ProjectDict,
):
    assert client.app

    # Establish guest session via a valid published project
    study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])
    await client.get(f"{study_url}")
    assert _is_user_authenticated(client.session)

    # Try to dispatch an unpublished project as guest
    dispatch_url = _dispatch_url(client, unpublished_project["uuid"])
    resp = await client.post(dispatch_url)
    assert resp.status in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ), f"GUEST must not dispatch unpublished project, got {resp.status}"

    # No copy must be created
    projects = await _get_user_projects(client)
    assert projects == [], f"No copy should have been created, got: {projects}"


# Phase 0 — Security Test 2: Unauthenticated POST is rejected
async def test_dispatch_endpoint_requires_authentication(
    studies_dispatcher_enabled: bool,
    client: TestClient,
    published_project: ProjectDict,
):
    assert client.app
    assert not _is_user_authenticated(client.session), "Must be anonymous"

    dispatch_url = _dispatch_url(client, published_project["uuid"])
    resp = await client.post(dispatch_url)
    assert resp.status in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ), f"Anonymous POST must be rejected, got {resp.status}"
