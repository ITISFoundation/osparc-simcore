# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""
Tests that project creation properly cleans up on failure.

Verifies:
- Fix 1: When director-v2 create_or_update_pipeline fails, the error propagates
  and the orphaned project is deleted.
- Fix 2: When any unexpected exception occurs after project insertion,
  the orphaned project is deleted.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    MockedStorageSubsystem,
    standard_role_response,
)
from servicelib.aiohttp import status
from servicelib.long_running_tasks.models import TaskStatus
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.director_v2.exceptions import DirectorV2ServiceError
from simcore_service_webserver.trash import trash_service
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

API_PREFIX = "/" + api_version_prefix

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def app_environment(
    use_in_memory_redis: RedisSettings,
    rabbit_settings: RabbitSettings,
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    envs_plugins = setenvs_from_dict(monkeypatch, {})
    return app_environment | envs_plugins


async def _get_all_projects_in_db(client: TestClient) -> list[dict]:
    """Directly query the DB for all projects (including hidden ones)."""
    assert client.app
    engine = get_asyncpg_engine(client.app)
    async with engine.connect() as conn:
        result = await conn.execute(sa.select(projects.c.uuid, projects.c.hidden))
        return [dict(row) for row in result.mappings()]


def _standard_user_role_response() -> tuple[str, list[tuple[UserRole, ExpectedResponse]]]:
    all_roles = standard_role_response()
    return (
        all_roles[0],
        [
            (user_role, response)
            for user_role, response in all_roles[1]
            if user_role not in [UserRole.ANONYMOUS, UserRole.GUEST]
        ],
    )


@pytest.mark.parametrize(*_standard_user_role_response())
async def test_create_project_cleans_up_on_director_v2_pipeline_failure(
    mock_dynamic_scheduler: None,
    client: TestClient,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    template_project: dict[str, Any],
    expected: ExpectedResponse,
    storage_subsystem_mock: MockedStorageSubsystem,
    project_db_cleaner: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    mocker: MockerFixture,
):
    """Test that when director-v2 create_or_update_pipeline fails,
    the project creation fails and the orphaned project is removed."""
    assert client.app

    # Override the mocked_dynamic_services_interface mock to raise DirectorV2ServiceError
    mocked_dynamic_services_interface["director_v2.api.create_or_update_pipeline"].side_effect = DirectorV2ServiceError(
        status=503, details="Service Unavailable"
    )

    # Attempt to create a project from template
    create_url = client.app.router["create_project"].url_for()
    create_url = create_url.with_query(from_study=template_project["uuid"])
    resp = await client.post(f"{create_url}", json={})
    data, _error = await assert_status(resp, expected.accepted)
    assert data
    status_url = data["status_href"]
    result_url = data["result_href"]

    # Wait for the long-running task to complete
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(60),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            result = await client.get(urlparse(status_url).path)
            data, _ = await assert_status(result, status.HTTP_200_OK)
            assert data
            task_status = TaskStatus.model_validate(data)
            assert task_status.done, f"Task not done yet: {task_status}"

    # The task should have failed
    result = await client.get(urlparse(result_url).path)
    assert result.status >= 400

    # NOTE: cleanup now only marks the orphaned project for immediate deletion
    # (hidden=True, trashed=epoch); actual removal happens exclusively via the
    # periodic trash-pruning GC, so trigger it explicitly here.
    await trash_service.safe_delete_expired_trash_as_admin(client.app)

    # CRITICAL: verify no orphan project remains in the DB.
    # Cleanup is scheduled asynchronously; retry until the orphan project disappears.
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            remaining_projects = await _get_all_projects_in_db(client)
            user_project_uuids = [p["uuid"] for p in remaining_projects if p["uuid"] != template_project["uuid"]]
            assert user_project_uuids == [], (
                f"Orphan project(s) left behind after pipeline failure: {user_project_uuids}"
            )


@pytest.mark.parametrize(*_standard_user_role_response())
async def test_create_project_cleans_up_on_unexpected_exception(
    mock_dynamic_scheduler: None,
    client: TestClient,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    template_project: dict[str, Any],
    expected: ExpectedResponse,
    storage_subsystem_mock: MockedStorageSubsystem,
    project_db_cleaner: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    mocker: MockerFixture,
):
    """Test that when an unexpected exception occurs after the project is inserted
    into the DB, the orphaned project is properly cleaned up."""
    assert client.app

    # Make the patch_project call (unhide step) raise an unexpected error
    mocker.patch(
        "simcore_service_webserver.projects._crud_api_create._projects_repository.patch_project",
        side_effect=RuntimeError("Unexpected DB connection error"),
    )

    # Spy on the cleanup function to verify it gets called
    delete_spy = mocker.patch(
        "simcore_service_webserver.projects._crud_api_create._trash_service.mark_for_immediate_deletion",
        new_callable=AsyncMock,  # don't call original (would fail since patch_project is mocked)
    )

    # Attempt to create a project from template (with copy_data=True to trigger unhide)
    create_url = client.app.router["create_project"].url_for()
    create_url = create_url.with_query(from_study=template_project["uuid"], copy_data="true")
    resp = await client.post(f"{create_url}", json={})
    data, _error = await assert_status(resp, expected.accepted)
    assert data
    status_url = data["status_href"]
    result_url = data["result_href"]

    # Wait for the long-running task to complete
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(60),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            result = await client.get(urlparse(status_url).path)
            data, _ = await assert_status(result, status.HTTP_200_OK)
            assert data
            task_status = TaskStatus.model_validate(data)
            assert task_status.done, f"Task not done yet: {task_status}"

    # The task should have failed
    result = await client.get(urlparse(result_url).path)
    assert result.status >= 400

    # CRITICAL: verify cleanup was attempted
    assert delete_spy.called, "mark_for_immediate_deletion was not called on failure"


@pytest.mark.parametrize(*_standard_user_role_response())
async def test_create_project_cleans_up_on_product_name_mismatch(
    mock_dynamic_scheduler: None,
    client: TestClient,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    template_project: dict[str, Any],
    expected: ExpectedResponse,
    storage_subsystem_mock: MockedStorageSubsystem,
    project_db_cleaner: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    mocker: MockerFixture,
):
    """Test: when a product-name mismatch triggers HTTPBadRequest after the project
    is inserted, the project must be cleaned up because this is a post-insertion
    failure that handles its own cleanup before raising."""
    assert client.app

    # Force an HTTPBadRequest by making get_project_product return a wrong product name
    mocker.patch(
        "simcore_service_webserver.projects._crud_api_create.ProjectDBAPI.get_project_product",
        return_value="wrong_product_name",
    )

    # Spy on the cleanup function — it SHOULD be called for post-insertion HTTP errors
    delete_spy = mocker.patch(
        "simcore_service_webserver.projects._crud_api_create._trash_service.mark_for_immediate_deletion",
        new_callable=AsyncMock,
    )

    # Attempt to create a project from template
    create_url = client.app.router["create_project"].url_for()
    create_url = create_url.with_query(from_study=template_project["uuid"])
    resp = await client.post(f"{create_url}", json={})
    data, _error = await assert_status(resp, expected.accepted)
    assert data
    status_url = data["status_href"]
    result_url = data["result_href"]

    # Wait for the long-running task to complete
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(60),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            result = await client.get(urlparse(status_url).path)
            data, _ = await assert_status(result, status.HTTP_200_OK)
            assert data
            task_status = TaskStatus.model_validate(data)
            assert task_status.done, f"Task not done yet: {task_status}"

    # The task should have failed with a 400
    result = await client.get(urlparse(result_url).path)
    assert result.status == status.HTTP_400_BAD_REQUEST

    # CRITICAL: verify cleanup WAS attempted — post-insertion HTTP errors handle their own cleanup
    assert delete_spy.called, "mark_for_immediate_deletion was not called for product-name mismatch"

    # NOTE: The project still exists because the spy mock prevents actual deletion.
    # The key assertion above verifies mark_for_immediate_deletion WAS called.
    remaining_projects = await _get_all_projects_in_db(client)
    user_project_uuids = [p["uuid"] for p in remaining_projects if p["uuid"] != template_project["uuid"]]
    assert len(user_project_uuids) == 1, f"Expected project to still exist (mocked deletion): {remaining_projects}"
