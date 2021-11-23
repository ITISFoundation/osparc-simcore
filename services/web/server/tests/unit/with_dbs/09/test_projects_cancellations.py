# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import asyncio
from typing import Any, Callable, Dict, List, Tuple

import pytest
from _helpers import ExpectedResponse  # type: ignore
from _helpers import MockedStorageSubsystem  # type: ignore
from _helpers import standard_role_response  # type: ignore
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver._meta import api_version_prefix
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

API_PREFIX = "/" + api_version_prefix


@pytest.fixture
async def slow_storage_subsystem_mock(
    storage_subsystem_mock: MockedStorageSubsystem,
) -> MockedStorageSubsystem:
    # requests storage to copy data
    async def _very_slow_copy_of_data(*args):
        await asyncio.sleep(30)
        return args[2]

    storage_subsystem_mock.copy_data_folders_from_project.side_effect = (
        _very_slow_copy_of_data
    )

    return storage_subsystem_mock


def standard_user_role_response() -> Tuple[
    str, List[Tuple[UserRole, ExpectedResponse]]
]:
    all_roles = standard_role_response()
    return (
        all_roles[0],
        [
            (user_role, response)
            for user_role, response in all_roles[1]
            if user_role not in [UserRole.ANONYMOUS, UserRole.GUEST]
        ],
    )


@pytest.mark.parametrize(*standard_user_role_response())
async def test_creating_new_project_from_template_and_disconnecting_does_not_create_project(
    client: TestClient,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    template_project: Dict[str, Any],
    expected: ExpectedResponse,
    catalog_subsystem_mock: Callable,
    slow_storage_subsystem_mock: MockedStorageSubsystem,
    project_db_cleaner: None,
):
    catalog_subsystem_mock([template_project])
    # create a project from another and disconnect while doing this by timing out
    # POST /v0/projects
    create_url = client.app.router["create_projects"].url_for()
    assert str(create_url) == f"{API_PREFIX}/projects"
    create_url = create_url.with_query(from_template=template_project["uuid"])
    with pytest.raises(asyncio.TimeoutError):
        await client.post(f"{create_url}", json={}, timeout=5)

    # let's check that there are no new project created, after timing out
    list_url = client.app.router["list_projects"].url_for()
    assert str(list_url) == API_PREFIX + "/projects"
    list_url = list_url.with_query(type="user")
    resp = await client.get(f"{list_url}")
    data, *_ = await assert_status(
        resp,
        expected.ok,
    )
    assert not data

    # NOTE: after coming back here timing-out, the code shall still run
    # in the server which is why we need to retry here
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(10), wait=wait_fixed(1)
    ):
        with attempt:
            slow_storage_subsystem_mock.delete_project.assert_called_once()


@pytest.mark.parametrize(*standard_user_role_response())
async def test_creating_new_project_as_template_and_disconnecting_does_not_create_project(
    client: TestClient,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    user_project: Dict[str, Any],
    expected: ExpectedResponse,
    catalog_subsystem_mock: Callable,
    slow_storage_subsystem_mock: MockedStorageSubsystem,
    project_db_cleaner: None,
):
    catalog_subsystem_mock([user_project])
    # create a project from another and disconnect while doing this by timing out
    # POST /v0/projects
    create_url = client.app.router["create_projects"].url_for()
    assert str(create_url) == f"{API_PREFIX}/projects"
    create_url = create_url.with_query(as_template=user_project["uuid"])
    with pytest.raises(asyncio.TimeoutError):
        await client.post(f"{create_url}", json={}, timeout=5)

    # let's check that there are no new project created, after timing out
    list_url = client.app.router["list_projects"].url_for()
    assert str(list_url) == API_PREFIX + "/projects"
    list_url = list_url.with_query(type="template")
    resp = await client.get(f"{list_url}")
    data, *_ = await assert_status(
        resp,
        expected.ok,
    )
    assert not data
    # NOTE: after coming back here timing-out, the code shall still run
    # in the server which is why we need to retry here
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(10), wait=wait_fixed(1)
    ):
        with attempt:
            slow_storage_subsystem_mock.delete_project.assert_called_once()


@pytest.mark.parametrize(*standard_user_role_response())
async def test_creating_new_project_from_template_without_copying_data_creates_skeleton(
    client: TestClient,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    template_project: Dict[str, Any],
    expected: ExpectedResponse,
    catalog_subsystem_mock: Callable,
    slow_storage_subsystem_mock: MockedStorageSubsystem,
    project_db_cleaner: None,
):
    catalog_subsystem_mock([template_project])
    # create a project from another without copying data shall not call in the storage API
    # POST /v0/projects
    create_url = client.app.router["create_projects"].url_for()
    assert str(create_url) == f"{API_PREFIX}/projects"
    create_url = create_url.with_query(
        from_template=template_project["uuid"], copy_data="false"
    )
    # this should go fast, let's have a timeout
    await client.post(f"{create_url}", json={}, timeout=2)

    slow_storage_subsystem_mock.copy_data_folders_from_project.assert_not_called()

    # we should have a new project without any data (meaning all the outputs, progress and run_hashes are empty)
    list_url = client.app.router["list_projects"].url_for()
    assert str(list_url) == API_PREFIX + "/projects"
    list_url = list_url.with_query(type="user")
    resp = await client.get(f"{list_url}")
    data, *_ = await assert_status(
        resp,
        expected.ok,
    )
    assert len(data) == 1
    project = data[0]
    assert "workbench" in project
    project_workbench = project["workbench"]
    assert project_workbench
    assert len(project_workbench) > 0
    EXPECTED_DELETED_FIELDS = ["outputs", "progress", "runHash"]
    for node_data in project_workbench.values():
        for field in EXPECTED_DELETED_FIELDS:
            assert field not in node_data


@pytest.mark.parametrize(*standard_user_role_response())
async def test_creating_new_project_as_template_without_copying_data_creates_skeleton(
    client: TestClient,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    user_project: Dict[str, Any],
    expected: ExpectedResponse,
    catalog_subsystem_mock: Callable,
    slow_storage_subsystem_mock: MockedStorageSubsystem,
    project_db_cleaner: None,
):
    catalog_subsystem_mock([user_project])
    # create a project from another without copying data shall not call in the storage API
    # POST /v0/projects
    create_url = client.app.router["create_projects"].url_for()
    assert str(create_url) == f"{API_PREFIX}/projects"
    create_url = create_url.with_query(
        as_template=user_project["uuid"], copy_data="false"
    )
    # this should go fast, let's have a timeout
    await client.post(f"{create_url}", json={}, timeout=2)

    slow_storage_subsystem_mock.copy_data_folders_from_project.assert_not_called()

    # we should have a new project without any data (meaning all the outputs, progress and run_hashes are empty)
    list_url = client.app.router["list_projects"].url_for()
    assert str(list_url) == API_PREFIX + "/projects"
    list_url = list_url.with_query(type="template")
    resp = await client.get(f"{list_url}")
    data, *_ = await assert_status(
        resp,
        expected.ok,
    )
    assert len(data) == 1
    project = data[0]
    assert "workbench" in project
    project_workbench = project["workbench"]
    assert project_workbench
    assert len(project_workbench) > 0
    EXPECTED_DELETED_FIELDS = ["outputs", "progress", "runHash"]
    for node_data in project_workbench.values():
        for field in EXPECTED_DELETED_FIELDS:
            assert field not in node_data
