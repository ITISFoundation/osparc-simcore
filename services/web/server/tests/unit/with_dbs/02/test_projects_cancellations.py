# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

import pytest
from aiohttp.test_utils import TestClient
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    MockedStorageSubsystem,
    standard_role_response,
)
from servicelib.aiohttp.long_running_tasks.client import LRTask
from servicelib.aiohttp.long_running_tasks.server import TaskGet, TaskProgress
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.application_settings import get_application_settings
from simcore_service_webserver.projects.models import ProjectDict
from tenacity.asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

API_PREFIX = "/" + api_version_prefix


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    envs_plugins = setenvs_from_dict(
        monkeypatch,
        {},
    )
    return app_environment | envs_plugins


@pytest.fixture
async def slow_storage_subsystem_mock(
    storage_subsystem_mock: MockedStorageSubsystem,
) -> MockedStorageSubsystem:
    # requests storage to copy data
    async def _very_slow_copy_of_data(*args):
        await asyncio.sleep(30)

        async def _mock_result():
            ...

        yield LRTask(progress=TaskProgress(), _result=_mock_result())

    storage_subsystem_mock.copy_data_folders_from_project.side_effect = (
        _very_slow_copy_of_data
    )

    return storage_subsystem_mock


def _standard_user_role_response() -> (
    tuple[str, list[tuple[UserRole, ExpectedResponse]]]
):
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
async def test_copying_large_project_and_aborting_correctly_removes_new_project(
    client: TestClient,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    user_project: dict[str, Any],
    expected: ExpectedResponse,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    slow_storage_subsystem_mock: MockedStorageSubsystem,
    project_db_cleaner: None,
):
    assert client.app
    catalog_subsystem_mock([user_project])
    # initiate a project copy that will last long (simulated by a long running storage)
    # POST /v0/projects
    create_url = client.app.router["create_project"].url_for()
    assert str(create_url) == f"{API_PREFIX}/projects"
    create_url = create_url.with_query(from_study=user_project["uuid"])
    resp = await client.post(f"{create_url}", json={})
    data, error = await assert_status(resp, expected.accepted)
    assert not error
    assert data
    assert "task_id" in data
    assert "status_href" in data
    assert "result_href" in data
    assert "abort_href" in data
    abort_url = data["abort_href"]

    # let's check that there are no new project created, while the copy is going on
    await asyncio.sleep(2)
    list_url = client.app.router["list_projects"].url_for()
    assert str(list_url) == API_PREFIX + "/projects"
    resp = await client.get(f"{list_url}")
    data, *_ = await assert_status(
        resp,
        expected.ok,
    )
    assert data
    assert len(data) == 1, "there are too many projects in the db!"

    # now abort the copy
    resp = await client.delete(urlparse(abort_url).path)
    await assert_status(resp, expected.no_content)
    # wait to check that the call to storage is "done"
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(10), wait=wait_fixed(1)
    ):
        with attempt:
            slow_storage_subsystem_mock.delete_project.assert_called_once()


@pytest.mark.parametrize(*_standard_user_role_response())
async def test_copying_large_project_and_retrieving_copy_task(
    client: TestClient,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    user_project: dict[str, Any],
    expected: ExpectedResponse,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    slow_storage_subsystem_mock: MockedStorageSubsystem,
    project_db_cleaner: None,
):
    assert client.app
    catalog_subsystem_mock([user_project])

    # initiate a project copy that will last long (simulated by a long running storage)
    # POST /v0/projects
    create_url = client.app.router["create_project"].url_for()
    assert str(create_url) == f"{API_PREFIX}/projects"
    create_url = create_url.with_query(from_study=user_project["uuid"])
    resp = await client.post(f"{create_url}", json={})
    data, error = await assert_status(resp, expected.accepted)
    created_copy_task = TaskGet.model_validate(data)
    # list current tasks
    list_task_url = client.app.router["list_tasks"].url_for()
    resp = await client.get(f"{list_task_url}")
    data, error = await assert_status(resp, expected.ok)
    assert data
    assert not error
    list_of_tasks = TypeAdapter(list[TaskGet]).validate_python(data)
    assert len(list_of_tasks) == 1
    task = list_of_tasks[0]
    assert task.task_name == f"POST {create_url}"
    # let the copy start
    await asyncio.sleep(2)
    # now abort the copy
    resp = await client.delete(urlparse(created_copy_task.abort_href).path)
    await assert_status(resp, expected.no_content)
    # wait to check that the call to storage is "done"
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(10), wait=wait_fixed(1)
    ):
        with attempt:
            slow_storage_subsystem_mock.delete_project.assert_called_once()


@pytest.mark.parametrize(*_standard_user_role_response())
async def test_creating_new_project_from_template_without_copying_data_creates_skeleton(
    client: TestClient,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    template_project: dict[str, Any],
    expected: ExpectedResponse,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    slow_storage_subsystem_mock: MockedStorageSubsystem,
    project_db_cleaner: None,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    assert client.app
    catalog_subsystem_mock([template_project])
    # create a project from another without copying data shall not call in the storage API
    # POST /v0/projects
    await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        from_study=template_project,
        copy_data=False,
    )

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


@pytest.mark.parametrize(*_standard_user_role_response())
async def test_creating_new_project_as_template_without_copying_data_creates_skeleton(
    client: TestClient,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    user_project: dict[str, Any],
    expected: ExpectedResponse,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    slow_storage_subsystem_mock: MockedStorageSubsystem,
    project_db_cleaner: None,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    assert client.app
    catalog_subsystem_mock([user_project])
    # create a project from another without copying data shall not call in the storage API
    # POST /v0/projects
    await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        from_study=user_project,
        copy_data=False,
        as_template=True,
    )

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


@pytest.mark.parametrize(*_standard_user_role_response())
async def test_copying_too_large_project_returns_422(
    client: TestClient,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    user_project: dict[str, Any],
    expected: ExpectedResponse,
    storage_subsystem_mock: MockedStorageSubsystem,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    assert client.app
    app_settings = get_application_settings(client.app)
    large_project_total_size = (
        app_settings.WEBSERVER_PROJECTS.PROJECTS_MAX_COPY_SIZE_BYTES + 1
    )
    storage_subsystem_mock.get_project_total_size_simcore_s3.return_value = TypeAdapter(
        ByteSize
    ).validate_python(large_project_total_size)

    # POST /v0/projects
    await request_create_project(
        client,
        expected.accepted,
        expected.unprocessable,
        logged_user,
        primary_group,
        from_study=user_project,
        copy_data=False,
        as_template=True,
    )
