# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple
from unittest import mock

import pytest
from _helpers import ExpectedResponse, standard_role_response
from aiohttp.test_utils import TestClient
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver._meta import api_version_prefix
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay

API_PREFIX = "/" + api_version_prefix


@dataclass
class MockedStorageSubsystem:
    copy_data_folders_from_project: mock.MagicMock
    delete_data_folders_of_project: mock.MagicMock


@pytest.fixture
async def slow_storage_subsystem_mock(
    loop: asyncio.AbstractEventLoop, mocker: MockerFixture
) -> MockedStorageSubsystem:
    # requests storage to copy data
    async def _very_slow_copy_of_data(*args):
        await asyncio.sleep(30)
        return args[2]

    mock = mocker.patch(
        "simcore_service_webserver.projects.projects_handlers.copy_data_folders_from_project",
        autospec=True,
        side_effect=_very_slow_copy_of_data,
    )

    # requests storage to delete data
    mock1 = mocker.patch(
        "simcore_service_webserver.projects.projects_handlers.projects_api.delete_data_folders_of_project",
        autospec=True,
        return_value="",
    )
    return MockedStorageSubsystem(mock, mock1)


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


@pytest.mark.parametrize("copy_query_param", ["from_template", "as_template"])
@pytest.mark.parametrize(*standard_user_role_response())
async def test_creating_new_project_and_disconnecting_does_not_create_project(
    client: TestClient,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    template_project: Dict[str, Any],
    expected: ExpectedResponse,
    catalog_subsystem_mock: Callable,
    slow_storage_subsystem_mock: MockedStorageSubsystem,
    project_db_cleaner: None,
    copy_query_param: str,
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
    async for attempt in AsyncRetrying(reraise=True, stop=stop_after_delay(10)):
        with attempt:
            list_url = client.app.router["list_projects"].url_for()
            assert str(list_url) == API_PREFIX + "/projects"
            list_url = list_url.with_query(type="user")
            resp = await client.get(f"{list_url}")
            data, *_ = await assert_status(
                resp,
                expected.ok,
            )
            assert not data
