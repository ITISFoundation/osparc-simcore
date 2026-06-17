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
from typing import Any
from unittest import mock

import pytest
import redis.asyncio as aioredis
from aiohttp import ClientResponse, ClientSession, web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request
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
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.redis import RedisClientSDK
from servicelib.redis._constants import DEFAULT_LOCK_TTL
from servicelib.rest_responses import unwrap_envelope
from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME
from simcore_service_webserver.garbage_collector.garbage_collector_service import (
    GUEST_USER_RC_LOCK_FORMAT,
)
from simcore_service_webserver.projects._projects_service import (
    submit_delete_project_task,
)
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.utils import NodesMap
from simcore_service_webserver.redis import get_redis_lock_manager_client_sdk
from simcore_service_webserver.studies_dispatcher._studies_access import (
    _copy_study_to_guest_protected_from_gc,
)
from simcore_service_webserver.users.users_service import (
    delete_user_without_projects,
    get_user_role,
)
from tenacity import retry, stop_after_attempt, wait_fixed

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

    # Mocks copy_data_folders_from_project BUT under studies_access
    mock = mocker.patch(
        "simcore_service_webserver.studies_dispatcher._studies_access.copy_data_folders_from_project",
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


@retry(wait=wait_fixed(5), stop=stop_after_attempt(3))
async def _assert_redirected_to_study(response: ClientResponse, session: ClientSession) -> str:
    # https://docs.aiohttp.org/en/stable/client_advanced.html#redirection-history
    assert len(response.history) == 1, "Is a re-direction"

    content = await response.text()
    assert response.status == status.HTTP_200_OK, f"Got {content}"

    # Expects redirection to osparc web
    assert response.url.path == "/"
    assert "OSPARC-SIMCORE" in content, f"Expected front-end rendering workbench's study, got {content!s}"

    # First check if the fragment indicates an error
    fragment = response.real_url.fragment
    error_match = re.match(r"/error", fragment)
    if error_match:
        # Parse query parameters to extract error details
        query_params = urllib.parse.parse_qs(fragment.split("?", 1)[1] if "?" in fragment else "")
        error_message = query_params.get("message", ["Unknown error"])[0]
        error_status = query_params.get("status_code", ["Unknown"])[0]

        pytest.fail(f"Redirected to error page: Status={error_status}, Message={error_message}")

    # Check for study path if not an error
    m = re.match(r"/study/([\d\w-]+)", fragment)
    assert m, f"Expected /study/uuid, got {fragment}"

    # Expects auth cookie for current user
    assert _is_user_authenticated(session)

    # returns newly created project
    return m.group(1)


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

    expected_prj_id = await _assert_redirected_to_study(resp, client.session)

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
    await _assert_redirected_to_study(resp, client.session)

    # user has a copy of the template project
    projects = await _get_user_projects(client)
    assert len(projects) == 1
    user_project = projects[0]

    # heck redirects to /#/study/{uuid}
    assert resp.real_url.fragment.endswith("/study/{}".format(user_project["uuid"]))
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

    await _assert_redirected_to_study(resp, client.session)

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

        delete_task = await submit_delete_project_task(
            app, prj_id, uid, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE, "osparc"
        )
        await delete_task

        await delete_user_without_projects(app, user_id=uid)
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

        expected_prj_id = await _assert_redirected_to_study(resp, client.session)

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
    Test that accessing /study returns 404 when studies_dispatcher_enabled is False.

    When the product has studies_dispatcher_enabled=False, the dispatcher feature
    should be completely disabled, and accessing the /study endpoint should result
    in a direct 404 response (not a redirect).
    """
    assert not _is_user_authenticated(client.session), "Is anonymous"
    assert client.app

    # Accessing the study should return 404 directly
    study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])
    resp = await client.get(f"{study_url}")

    assert resp.status == status.HTTP_404_NOT_FOUND, (
        f"Expected 404 when studies_dispatcher_enabled=False, got {resp.status}"
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
    Test that accessing /study returns 404 for logged-in users when
    studies_dispatcher_enabled is False.

    Even logged-in users should not be able to access the dispatcher
    when the feature is disabled at the product level.
    """
    assert _is_user_authenticated(client.session), "Is already logged-in"
    assert client.app

    # Accessing the study should return 404 directly, even for authenticated users
    study_url = client.app.router["get_redirection_to_study_page"].url_for(id=published_project["uuid"])
    resp = await client.get(f"{study_url}")

    assert resp.status == status.HTTP_404_NOT_FOUND, (
        f"Expected 404 when studies_dispatcher_enabled=False, got {resp.status}"
    )


async def _is_guest_gc_lock_held(redis_sdk: RedisClientSDK, guest_user_name: str) -> bool:
    # The garbage-collector skips a guest whenever the construction GC lock (keyed by the
    # guest name) is held (see garbage_collector._core_guests, `lock_during_construction`).
    # Hence checking the key existence is equivalent to checking that the GC would skip the guest.
    lock_key = GUEST_USER_RC_LOCK_FORMAT.format(user_id=guest_user_name)
    return bool(await redis_sdk.redis.exists(lock_key))


async def test_guest_gc_lock_is_renewed_and_not_released_during_long_study_copy(
    studies_dispatcher_enabled: bool,
    client: TestClient,
    mocker: MockerFixture,
    faker: Faker,
    # needed to cleanup the locks between parametrizations
    redis_locks_client: AsyncIterator[aioredis.Redis],
):
    """
    Ensures that the guest-user GC lock held around the (potentially long) study copy
    is NOT released while the copy takes longer than the lock TTL, because it is
    auto-extended (renewed) by `exclusive`.

    While the lock is held the garbage-collector would skip the guest (it checks the
    very same construction key keyed by the guest name), so the guest user and its
    destination project cannot be deleted mid-copy.
    """
    assert client.app
    redis_sdk = get_redis_lock_manager_client_sdk(client.app)

    guest_user_name = faker.pystr().lower()
    user = {
        "id": faker.pyint(min_value=1000, max_value=99999),
        "name": guest_user_name,
        "role": UserRole.GUEST,
        "email": faker.email(),
    }
    template_project = {"uuid": faker.uuid4()}
    request = make_mocked_request("GET", "/", app=client.app)

    # the copy intentionally takes LONGER than the lock TTL to force at least one renewal
    copy_duration_s = DEFAULT_LOCK_TTL.total_seconds() + 3.0

    copy_started = asyncio.Event()

    async def _slow_copy(_request, _template_project, _user) -> str:
        copy_started.set()
        await asyncio.sleep(copy_duration_s)
        return "copied-project-uuid"

    mocker.patch(
        "simcore_service_webserver.studies_dispatcher._studies_access.copy_study_to_account",
        side_effect=_slow_copy,
    )

    # initially not locked
    assert not await _is_guest_gc_lock_held(redis_sdk, guest_user_name)

    copy_task = asyncio.create_task(_copy_study_to_guest_protected_from_gc(request, template_project, user))
    await asyncio.wait_for(copy_started.wait(), timeout=5)

    # poll across more than one TTL window: without renewal the lock would expire at
    # DEFAULT_LOCK_TTL and this assertion would fail once we cross that boundary
    elapsed = 0.0
    poll_interval = 1.0
    while elapsed < copy_duration_s - poll_interval:
        assert await _is_guest_gc_lock_held(redis_sdk, guest_user_name), (
            f"guest GC lock was released after {elapsed}s (TTL={DEFAULT_LOCK_TTL.total_seconds()}s): "
            "exclusive did not renew it"
        )
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    assert await copy_task == "copied-project-uuid"

    # once the copy is done the lock is released and the guest becomes GC-eligible again
    assert not await _is_guest_gc_lock_held(redis_sdk, guest_user_name)
