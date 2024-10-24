# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from copy import deepcopy
from datetime import datetime
from typing import Any

import pytest
from aiohttp.client_exceptions import ClientResponseError
from aiohttp.test_utils import TestClient
from aiohttp.web_exceptions import HTTPNotFound
from faker import Faker
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.projects import ProjectID
from pydantic import TypeAdapter
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    MockedStorageSubsystem,
    standard_role_response,
)
from servicelib.aiohttp import status
from servicelib.aiohttp.long_running_tasks.client import long_running_task_request
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict
from yarl import URL


@pytest.fixture
def fake_project(
    fake_project: ProjectDict, workbench_db_column: dict[str, Any]
) -> ProjectDict:
    # OVERRIDES user_project
    project = deepcopy(fake_project)
    project["workbench"] = workbench_db_column
    return project


async def _request_clone_project(client: TestClient, url: URL) -> ProjectGet:
    """Raise HTTPError subclasses if request fails"""
    # polls until long-running task is done
    data = None
    async for long_running_task in long_running_task_request(
        client.session, url=client.make_url(url.path), json=None, client_timeout=30
    ):
        print(f"{long_running_task.progress=}")
        if long_running_task.done():
            data = await long_running_task.result()

    assert data is not None
    return ProjectGet.model_validate(data)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_clone_project_user_permissions(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    # mocks backend
    storage_subsystem_mock: MockedStorageSubsystem,
    mock_catalog_service_api_responses: None,
    project_db_cleaner: None,
    expected,
):
    assert client.app

    project = user_project

    url = client.app.router["clone_project"].url_for(project_id=project["uuid"])
    assert f"/v0/projects/{project['uuid']}:clone" == url.path

    try:
        cloned_project = await _request_clone_project(client, url)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        assert exc.status == expected.ok  # pylint: disable=no-member

    if expected.ok == status.HTTP_200_OK:
        # check whether it's a clone
        assert ProjectID(project["uuid"]) != cloned_project.uuid


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_clone_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    # mocks backend
    storage_subsystem_mock: MockedStorageSubsystem,
    mock_catalog_service_api_responses: None,
    project_db_cleaner: None,
):
    assert client.app

    project = user_project

    url = client.app.router["clone_project"].url_for(project_id=project["uuid"])
    assert f"/v0/projects/{project['uuid']}:clone" == url.path

    cloned_project = await _request_clone_project(client, url)

    # check whether it's a clone
    assert ProjectID(project["uuid"]) != cloned_project.uuid
    assert project["description"] == cloned_project.description
    assert TypeAdapter(datetime).validate_python(project["creationDate"]) < TypeAdapter(
        datetime
    ).validate_python(cloned_project.creation_date)

    assert len(project["workbench"]) == len(cloned_project.workbench)
    assert set(project["workbench"].keys()) != set(
        cloned_project.workbench.keys()
    ), "clone does NOT preserve node ids"


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_clone_invalid_project_responds_not_found(
    client: TestClient,
    logged_user: UserInfoDict,
    # mocks backend
    storage_subsystem_mock: MockedStorageSubsystem,
    mock_catalog_service_api_responses: None,
    project_db_cleaner: None,
    faker: Faker,
):
    assert client.app

    invalid_project_id = faker.uuid4()

    url = client.app.router["clone_project"].url_for(project_id=invalid_project_id)
    assert f"/v0/projects/{invalid_project_id}:clone" == url.path

    with pytest.raises(ClientResponseError) as err_info:
        await _request_clone_project(client, url)

    assert err_info.value.status == HTTPNotFound.status_code
