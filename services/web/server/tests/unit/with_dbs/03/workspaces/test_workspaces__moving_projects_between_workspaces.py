# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


from copy import deepcopy
from http import HTTPStatus

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from pytest_simcore.helpers.webserver_projects import create_project
from servicelib.aiohttp import status
from simcore_postgres_database.models.projects_to_folders import projects_to_folders
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def mock_catalog_api_get_services_for_user_in_product(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.projects._crud_api_read.get_services_for_user_in_product",
        spec=True,
        return_value=[],
    )
    mocker.patch(
        "simcore_service_webserver.projects._crud_handlers.get_services_for_user_in_product",
        spec=True,
        return_value=[],
    )
    mocker.patch(
        "simcore_service_webserver.projects._crud_handlers.project_uses_available_services",
        spec=True,
        return_value=True,
    )


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_moving_between_workspaces_user_role_permissions(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    mock_catalog_api_get_services_for_user_in_product: MockerFixture,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
):
    # Move project from workspace to your private workspace
    base_url = client.app.router["replace_project_workspace"].url_for(
        project_id=fake_project["uuid"], workspace_id="null"
    )
    resp = await client.put(base_url)
    await assert_status(resp, expected.no_content)


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_moving_between_private_and_shared_workspaces(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_api_get_services_for_user_in_product: MockerFixture,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
):
    assert client.app

    # create a new workspace
    url = client.app.router["create_workspace"].url_for()
    resp = await client.post(
        url.path,
        json={
            "name": "My first workspace",
            "description": "Custom description",
            "thumbnail": None,
        },
    )
    added_workspace, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # Create project in workspace
    project_data = deepcopy(fake_project)
    project_data["workspace_id"] = f"{added_workspace['workspaceId']}"
    project = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )

    # Get project in workspace
    base_url = client.app.router["get_project"].url_for(project_id=project["uuid"])
    resp = await client.get(base_url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["workspaceId"] == added_workspace["workspaceId"]  # <-- Workspace ID

    # Move project from workspace to your private workspace
    base_url = client.app.router["replace_project_workspace"].url_for(
        project_id=project["uuid"], workspace_id="null"
    )
    resp = await client.put(base_url)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Get project in workspace
    base_url = client.app.router["get_project"].url_for(project_id=project["uuid"])
    resp = await client.get(base_url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["workspaceId"] is None  # <-- Workspace ID is None

    # Move project from your private workspace to shared workspace
    base_url = client.app.router["replace_project_workspace"].url_for(
        project_id=project["uuid"], workspace_id=f"{added_workspace['workspaceId']}"
    )
    resp = await client.put(base_url)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Get project in workspace
    base_url = client.app.router["get_project"].url_for(project_id=project["uuid"])
    resp = await client.get(base_url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["workspaceId"] == added_workspace["workspaceId"]  # <-- Workspace ID


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_moving_between_shared_and_shared_workspaces(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_api_get_services_for_user_in_product: MockerFixture,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
):
    assert client.app

    # create a new workspace
    url = client.app.router["create_workspace"].url_for()
    resp = await client.post(
        url.path,
        json={
            "name": "My first workspace",
            "description": "Custom description",
            "thumbnail": None,
        },
    )
    added_workspace, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # Create project in workspace
    project_data = deepcopy(fake_project)
    project_data["workspace_id"] = f"{added_workspace['workspaceId']}"
    project = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )

    # create a second new workspace
    url = client.app.router["create_workspace"].url_for()
    resp = await client.post(
        url.path,
        json={
            "name": "My second workspace",
            "description": "Custom description",
            "thumbnail": None,
        },
    )
    second_workspace, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # Get project in workspace
    base_url = client.app.router["get_project"].url_for(project_id=project["uuid"])
    resp = await client.get(base_url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["workspaceId"] == added_workspace["workspaceId"]  # <-- Workspace ID

    # Move project from workspace to your private workspace
    base_url = client.app.router["replace_project_workspace"].url_for(
        project_id=project["uuid"], workspace_id=f"{second_workspace['workspaceId']}"
    )
    resp = await client.put(base_url)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Get project in workspace
    base_url = client.app.router["get_project"].url_for(project_id=project["uuid"])
    resp = await client.get(base_url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["workspaceId"] == second_workspace["workspaceId"]  # <-- Workspace ID


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_moving_between_workspaces_check_removed_from_folder(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_api_get_services_for_user_in_product: MockerFixture,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
    postgres_db: sa.engine.Engine,
):
    assert client.app

    # create a new workspace
    url = client.app.router["create_workspace"].url_for()
    resp = await client.post(
        url.path,
        json={
            "name": "My first workspace",
            "description": "Custom description",
            "thumbnail": None,
        },
    )
    added_workspace, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # Create project in workspace
    project_data = deepcopy(fake_project)
    project_data["workspace_id"] = f"{added_workspace['workspaceId']}"
    project = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )

    # Create folder in workspace
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        url.path,
        json={
            "name": "Original user folder",
            "workspaceId": f"{added_workspace['workspaceId']}",
        },
    )
    first_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # Move project in specific folder in workspace
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{first_folder['folderId']}",
        project_id=f"{project['uuid']}",
    )
    resp = await client.put(url.path)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Check project_to_folders DB is not empty
    with postgres_db.connect() as con:
        count_query = sa.select(sa.func.count()).select_from(projects_to_folders)
        result = con.execute(count_query).scalar()
    assert result == 1

    # Get project in workspace
    base_url = client.app.router["get_project"].url_for(project_id=project["uuid"])
    resp = await client.get(base_url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["workspaceId"] == added_workspace["workspaceId"]  # <-- Workspace ID

    # Move project from workspace to your private workspace
    base_url = client.app.router["replace_project_workspace"].url_for(
        project_id=project["uuid"], workspace_id="none"
    )
    resp = await client.put(base_url)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Get project in workspace
    base_url = client.app.router["get_project"].url_for(project_id=project["uuid"])
    resp = await client.get(base_url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["workspaceId"] is None  # <-- Workspace ID is None

    # Check project_to_folders DB is empty
    with postgres_db.connect() as con:
        count_query = sa.select(sa.func.count()).select_from(projects_to_folders)
        result = con.execute(count_query).scalar()
    assert result == 0
