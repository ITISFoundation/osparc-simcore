# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import asyncio
from http import HTTPStatus
from unittest import mock

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.folders_v2 import FolderGet
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser, UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from servicelib.aiohttp import status
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects._groups_db import (
    GroupID,
    update_or_insert_project_group,
)
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_folders_user_role_permissions(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: ExpectedResponse,
):
    assert client.app

    url = client.app.router["list_folders"].url_for()
    resp = await client.get(f"{url}")
    await assert_status(resp, expected.ok)


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_folders_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    assert client.app

    # list user folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []

    # create a new folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(f"{url}", json={"name": "My first folder"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    added_folder = FolderGet.model_validate(data)

    # list user folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(f"{url}")
    data, _, meta, links = await assert_status(
        resp, status.HTTP_200_OK, include_meta=True, include_links=True
    )
    assert len(data) == 1
    assert data[0]["folderId"] == added_folder.folder_id
    assert data[0]["name"] == added_folder.name
    assert meta["count"] == 1
    assert links

    # get a user folder
    url = client.app.router["get_folder"].url_for(folder_id=f"{added_folder.folder_id}")
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got_folder = FolderGet.model_validate(data)
    assert got_folder.folder_id == added_folder.folder_id
    assert got_folder.name == added_folder.name

    # update a folder
    url = client.app.router["replace_folder"].url_for(
        folder_id=f"{added_folder.folder_id}"
    )
    resp = await client.put(
        f"{url}",
        json={"name": "My Second folder"},
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    updated_folder = FolderGet.model_validate(data)
    assert updated_folder.folder_id == got_folder.folder_id
    assert updated_folder.name != got_folder.name

    # list user folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["name"] == "My Second folder"

    # delete a folder
    url = client.app.router["delete_folder"].url_for(
        folder_id=f"{added_folder.folder_id}"
    )
    resp = await client.delete(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # list user folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_sub_folders_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    assert client.app

    # list user folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []

    # create a new folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(f"{url}", json={"name": "My first folder"})
    root_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # create a subfolder folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "My subfolder",
            "parentFolderId": root_folder["folderId"],
        },
    )
    subfolder_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # list user root folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["name"] == "My first folder"

    # list user specific folder
    url = (
        client.app.router["list_folders"]
        .url_for()
        .with_query({"folder_id": f"{subfolder_folder['folderId']}"})
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 0

    # create a sub sub folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "My sub sub folder",
            "parentFolderId": subfolder_folder["folderId"],
        },
    )
    subsubfolder_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # list user subfolder folders
    url = (
        client.app.router["list_folders"]
        .url_for()
        .with_query({"folder_id": f"{subfolder_folder['folderId']}"})
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["name"] == "My sub sub folder"
    assert data[0]["parentFolderId"] == subfolder_folder["folderId"]

    # try to move sub folder to sub sub folder (should not be allowed to)
    url = client.app.router["replace_folder"].url_for(
        folder_id=f"{subfolder_folder['folderId']}",
    )
    resp = await client.put(
        f"{url}",
        json={
            "name": "My Updated Folder",
            "parentFolderId": f"{subsubfolder_folder['folderId']}",
        },
    )
    await assert_status(resp, status.HTTP_409_CONFLICT)

    # move sub sub folder to root folder
    url = client.app.router["replace_folder"].url_for(
        folder_id=f"{subsubfolder_folder['folderId']}"
    )
    resp = await client.put(
        f"{url}",
        json={
            "name": "My Updated Folder",
            "parentFolderId": None,
        },
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert FolderGet.model_validate(data)

    # list user root folders
    url = client.app.router["list_folders"].url_for().with_query({"folder_id": "null"})
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 2


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_project_folder_movement_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    assert client.app

    # create a new folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(f"{url}", json={"name": "My first folder"})
    root_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # add project to the folder
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{root_folder['folderId']}", project_id=f"{user_project['uuid']}"
    )
    resp = await client.put(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # create a sub folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "My sub folder",
            "parentFolderId": root_folder["folderId"],
        },
    )
    sub_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # move project to the sub folder
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{sub_folder['folderId']}", project_id=f"{user_project['uuid']}"
    )
    resp = await client.put(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # move project to the root directory
    url = client.app.router["replace_project_folder"].url_for(
        folder_id="null", project_id=f"{user_project['uuid']}"
    )
    resp = await client.put(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)


@pytest.fixture
def mock_catalog_api_get_services_for_user_in_product(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.projects._crud_api_read.get_services_for_user_in_product",
        spec=True,
        return_value=[],
    )


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_project_listing_inside_of_private_folder(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_api_get_services_for_user_in_product: MockerFixture,
):
    assert client.app

    # create a new folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(f"{url}", json={"name": "My first folder"})
    original_user_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # add project to the folder
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{original_user_folder['folderId']}",
        project_id=f"{user_project['uuid']}",
    )
    resp = await client.put(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # list project in user private folder
    url = (
        client.app.router["list_projects"]
        .url_for()
        .with_query({"folder_id": f"{original_user_folder['folderId']}"})
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == user_project["uuid"]
    assert data[0]["workspaceId"] is None
    assert data[0]["folderId"] == original_user_folder["folderId"]

    # Create new user
    async with LoggedUser(client) as new_logged_user:
        # Try to list folder that user doesn't have access to
        url = (
            client.app.router["list_projects"]
            .url_for()
            .with_query({"folder_id": f"{original_user_folder['folderId']}"})
        )
        resp = await client.get(f"{url}")
        _, errors = await assert_status(resp, status.HTTP_403_FORBIDDEN)
        assert errors

        # Now we will share the project with the new user
        await update_or_insert_project_group(
            client.app,
            project_id=user_project["uuid"],
            group_id=TypeAdapter(GroupID).validate_python(
                new_logged_user["primary_gid"]
            ),
            read=True,
            write=True,
            delete=False,
        )

        # list new user root folder
        url = (
            client.app.router["list_projects"]
            .url_for()
            .with_query({"folder_id": "null"})
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 1
        assert data[0]["uuid"] == user_project["uuid"]
        assert data[0]["workspaceId"] is None
        assert data[0]["folderId"] is None

        # create a new folder
        url = client.app.router["create_folder"].url_for()
        resp = await client.post(f"{url}", json={"name": "New user folder"})
        new_user_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

        # add project to the folder
        url = client.app.router["replace_project_folder"].url_for(
            folder_id=f"{new_user_folder['folderId']}",
            project_id=f"{user_project['uuid']}",
        )
        resp = await client.put(f"{url}")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        # list new user specific folder
        url = (
            client.app.router["list_projects"]
            .url_for()
            .with_query({"folder_id": f"{new_user_folder['folderId']}"})
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 1
        assert data[0]["uuid"] == user_project["uuid"]
        assert data[0]["workspaceId"] is None
        assert data[0]["folderId"] == new_user_folder["folderId"]


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
async def test_folders_deletion(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_api_get_services_for_user_in_product: MockerFixture,
    mock_storage_delete_data_folders: mock.Mock,
):
    assert client.app

    # create a new folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(f"{url}", json={"name": "My first folder"})
    root_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)
    assert FolderGet.model_validate(root_folder)

    # create a subfolder folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "My subfolder 1",
            "parentFolderId": root_folder["folderId"],
        },
    )
    subfolder_1, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # create a subfolder folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "My subfolder 2",
            "parentFolderId": root_folder["folderId"],
        },
    )
    subfolder_2, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # add project to the sub folder
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{subfolder_2['folderId']}",
        project_id=f"{user_project['uuid']}",
    )
    resp = await client.put(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # create a sub sub folder folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "My sub sub folder",
            "parentFolderId": subfolder_1["folderId"],
        },
    )
    await assert_status(resp, status.HTTP_201_CREATED)

    # list user folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1

    # list subfolder projects
    url = (
        client.app.router["list_projects"]
        .url_for()
        .with_query({"folder_id": f"{subfolder_2['folderId']}"})
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == user_project["uuid"]

    # list root projects
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 0

    # delete a subfolder
    url = client.app.router["delete_folder"].url_for(
        folder_id=f"{subfolder_1['folderId']}"
    )
    resp = await client.delete(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # delete a root folder
    url = client.app.router["delete_folder"].url_for(
        folder_id=f"{root_folder['folderId']}"
    )
    resp = await client.delete(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    fire_and_forget_task: asyncio.Task = next(
        iter(client.app[APP_FIRE_AND_FORGET_TASKS_KEY])
    )
    assert fire_and_forget_task.get_name().startswith(
        "fire_and_forget_task_delete_project_task_"
    )
    await fire_and_forget_task
    assert len(client.app[APP_FIRE_AND_FORGET_TASKS_KEY]) == 0

    # list root projects (The project should have been deleted)
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 0
