# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import asyncio
from copy import deepcopy
from http import HTTPStatus
from unittest import mock

import pytest
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser, UserInfoDict
from pytest_simcore.helpers.webserver_projects import create_project
from pytest_simcore.helpers.webserver_workspaces import update_or_insert_workspace_group
from servicelib.aiohttp import status
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
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


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_workspaces_full_workflow_with_folders_and_projects(
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

    # List project in workspace
    base_url = client.app.router["list_projects"].url_for()
    url = base_url.with_query({"workspace_id": f"{added_workspace['workspaceId']}"})
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == project["uuid"]

    # Get project in workspace
    base_url = client.app.router["get_project"].url_for(project_id=project["uuid"])
    resp = await client.get(base_url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["uuid"] == project["uuid"]

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

    # List folders in workspace
    base_url = client.app.router["list_folders"].url_for()
    url = base_url.with_query(
        {"workspace_id": f"{added_workspace['workspaceId']}", "folder_id": "null"}
    )
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["folderId"] == first_folder["folderId"]

    # Move project in specific folder in workspace
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{first_folder['folderId']}",
        project_id=f"{project['uuid']}",
    )
    resp = await client.put(url.path)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # List projects in specific folder in workspace
    base_url = client.app.router["list_projects"].url_for()
    url = base_url.with_query(
        {
            "workspace_id": f"{added_workspace['workspaceId']}",
            "folder_id": f"{first_folder['folderId']}",
        }
    )
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == project["uuid"]

    # Create new user
    async with LoggedUser(client) as new_logged_user:
        # Try to list folder that user doesn't have access to
        base_url = client.app.router["list_projects"].url_for()
        url = base_url.with_query({"workspace_id": f"{added_workspace['workspaceId']}"})
        resp = await client.get(url)
        _, errors = await assert_status(
            resp,
            status.HTTP_401_UNAUTHORIZED,
        )
        assert errors

        # Now we will share the workspace with the new user
        await update_or_insert_workspace_group(
            client.app,
            workspace_id=added_workspace["workspaceId"],
            group_id=new_logged_user["primary_gid"],
            read=True,
            write=True,
            delete=False,
        )

        # New user list root folders inside of workspace
        base_url = client.app.router["list_folders"].url_for()
        url = base_url.with_query(
            {"workspace_id": f"{added_workspace['workspaceId']}", "folder_id": "null"}
        )
        resp = await client.get(url)
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 1

        # New user list root projects inside of workspace
        base_url = client.app.router["list_projects"].url_for()
        url = base_url.with_query(
            {
                "workspace_id": f"{added_workspace['workspaceId']}",
                "folder_id": "none",
            }
        )
        resp = await client.get(url)
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 0

        # New user list projects in specific folder inside of workspace
        base_url = client.app.router["list_projects"].url_for()
        url = base_url.with_query(
            {
                "workspace_id": f"{added_workspace['workspaceId']}",
                "folder_id": f"{first_folder['folderId']}",
            }
        )
        resp = await client.get(url)
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 1
        assert data[0]["uuid"] == project["uuid"]

        # New user with write permission creates a folder
        url = client.app.router["create_folder"].url_for()
        resp = await client.post(
            url.path,
            json={
                "name": "New user folder",
                "workspaceId": f"{added_workspace['workspaceId']}",
            },
        )
        await assert_status(resp, status.HTTP_201_CREATED)

        # Now we will remove write permissions
        await update_or_insert_workspace_group(
            client.app,
            workspace_id=added_workspace["workspaceId"],
            group_id=new_logged_user["primary_gid"],
            read=True,
            write=False,
            delete=False,
        )

        # Now error is raised on the creation of folder as user doesn't have write access
        url = client.app.router["create_folder"].url_for()
        resp = await client.post(
            url.path,
            json={
                "name": "New user second folder",
                "workspaceId": f"{added_workspace['workspaceId']}",
            },
        )
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        # But user has still read permissions
        base_url = client.app.router["list_folders"].url_for()
        url = base_url.with_query(
            {"workspace_id": f"{added_workspace['workspaceId']}", "folder_id": "null"}
        )
        resp = await client.get(url)
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 2


@pytest.fixture
def mock_storage_delete_data_folders(mocker: MockerFixture) -> mock.Mock:
    mocker.patch(
        "simcore_service_webserver.dynamic_scheduler.api.list_dynamic_services",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.projects.projects_api.remove_project_dynamic_services",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.projects._crud_api_delete.api.delete_pipeline",
        autospec=True,
    )
    return mocker.patch(
        "simcore_service_webserver.projects._crud_api_delete.delete_data_folders_of_project",
        return_value=None,
    )


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_workspaces_delete_folders(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_api_get_services_for_user_in_product: MockerFixture,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
    mock_storage_delete_data_folders: mock.Mock,
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
    first_project = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )
    second_project = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )

    # List project in workspace
    base_url = client.app.router["list_projects"].url_for()
    url = base_url.with_query({"workspace_id": f"{added_workspace['workspaceId']}"})
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 2

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

    # Create sub folder of previous folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        url.path,
        json={
            "name": "Second user folder",
            "workspaceId": f"{added_workspace['workspaceId']}",
            "parentFolderId": f"{first_folder['folderId']}",
        },
    )
    second_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # Move first project in specific folder in workspace
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{first_folder['folderId']}",
        project_id=f"{first_project['uuid']}",
    )
    resp = await client.put(url.path)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Move second project in specific folder in workspace
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{second_folder['folderId']}",
        project_id=f"{second_project['uuid']}",
    )
    resp = await client.put(url.path)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Delete folder
    url = client.app.router["delete_folder"].url_for(
        folder_id=f"{first_folder['folderId']}"
    )
    resp = await client.delete(url.path)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    fire_and_forget_tasks = client.app[APP_FIRE_AND_FORGET_TASKS_KEY]
    t1: asyncio.Task = list(fire_and_forget_tasks)[0]
    t2: asyncio.Task = list(fire_and_forget_tasks)[1]
    assert t1.get_name().startswith("fire_and_forget_task_delete_project_task_")
    assert t2.get_name().startswith("fire_and_forget_task_delete_project_task_")
    await t1
    await t2

    assert len(client.app[APP_FIRE_AND_FORGET_TASKS_KEY]) == 0

    # List project in workspace (The projects should have been deleted)
    base_url = client.app.router["list_projects"].url_for()
    url = base_url.with_query({"workspace_id": f"{added_workspace['workspaceId']}"})
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 0
