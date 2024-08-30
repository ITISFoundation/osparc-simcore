# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.folders_v2 import FolderGet
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


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
    resp = await client.get(url.path)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []

    # create a new folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(url.path, json={"name": "My first folder"})
    added_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)
    assert FolderGet.parse_obj(added_folder)

    # list user folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(url.path)
    data, _, meta, links = await assert_status(
        resp, status.HTTP_200_OK, include_meta=True, include_links=True
    )
    assert len(data) == 1
    assert data[0]["folderId"] == added_folder["folderId"]
    assert data[0]["name"] == "My first folder"
    assert meta["count"] == 1
    assert links

    # get a user folder
    url = client.app.router["get_folder"].url_for(
        folder_id=f"{added_folder['folderId']}"
    )
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["folderId"] == added_folder["folderId"]
    assert data["name"] == "My first folder"

    # update a folder
    url = client.app.router["replace_folder"].url_for(
        folder_id=f"{added_folder['folderId']}"
    )
    resp = await client.put(
        url.path,
        json={
            "name": "My Second folder",
        },
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert FolderGet.parse_obj(data)

    # list user folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(url.path)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["name"] == "My Second folder"

    # delete a folder
    url = client.app.router["delete_folder"].url_for(
        folder_id=f"{added_folder['folderId']}"
    )
    resp = await client.delete(url.path)
    data, _ = await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # list user folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(url.path)
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
    resp = await client.get(url.path)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []

    # create a new folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(url.path, json={"name": "My first folder"})
    root_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # create a subfolder folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        url.path,
        json={
            "name": "My subfolder",
            "parentFolderId": root_folder["folderId"],
        },
    )
    subfolder_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # list user root folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(url.path)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["name"] == "My first folder"

    # list user specific folder
    base_url = client.app.router["list_folders"].url_for()
    url = base_url.with_query({"folder_id": f"{subfolder_folder['folderId']}"})
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 0

    # create a sub sub folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        url.path,
        json={
            "name": "My sub sub folder",
            "parentFolderId": subfolder_folder["folderId"],
        },
    )
    subsubfolder_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # list user subfolder folders
    base_url = client.app.router["list_folders"].url_for()
    url = base_url.with_query({"folder_id": f"{subfolder_folder['folderId']}"})
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["name"] == "My sub sub folder"
    assert data[0]["parentFolderId"] == subfolder_folder["folderId"]

    # move sub sub folder to root folder
    url = client.app.router["replace_folder"].url_for(
        folder_id=f"{subsubfolder_folder['folderId']}"
    )
    resp = await client.put(
        url.path,
        json={
            "name": "My Updated Folder",
            "parentFolderId": None,
        },
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert FolderGet.parse_obj(data)

    # list user root folders
    base_url = client.app.router["list_folders"].url_for()
    url = base_url.with_query({"folder_id": "null"})
    resp = await client.get(url)
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
    resp = await client.post(url.path, json={"name": "My first folder"})
    root_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # add project to the folder
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{root_folder['folderId']}", project_id=f"{user_project['uuid']}"
    )
    resp = await client.put(url.path)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # create a sub folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        url.path,
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
    resp = await client.put(url.path)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # move project to the root directory
    url = client.app.router["replace_project_folder"].url_for(
        folder_id="null", project_id=f"{user_project['uuid']}"
    )
    resp = await client.put(url.path)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)


# @pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
# async def test_project_folder_movement_full_workflow_shared_workspace(
#     client: TestClient,
#     logged_user: UserInfoDict,
#     user_project: ProjectDict,
#     expected: HTTPStatus,
# ):
#     assert client.app
#     # create a workspace


#     # create a new folder
#     url = client.app.router["create_folder"].url_for()
#     resp = await client.post(url.path, json={"name": "My first folder", "workspace_id": 1})
#     root_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

#     # add project to the folder
#     url = client.app.router["replace_project_folder"].url_for(
#         folder_id=f"{root_folder['folderId']}", project_id=f"{user_project['uuid']}"
#     )
#     resp = await client.put(url.path)
#     await assert_status(resp, status.HTTP_204_NO_CONTENT)

#     # create a sub folder
#     url = client.app.router["create_folder"].url_for()
#     resp = await client.post(
#         url.path,
#         json={
#             "name": "My sub folder",
#             "parentFolderId": root_folder["folderId"],
#         },
#     )
#     sub_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

#     # move project to the sub folder
#     url = client.app.router["replace_project_folder"].url_for(
#         folder_id=f"{sub_folder['folderId']}", project_id=f"{user_project['uuid']}"
#     )
#     resp = await client.put(url.path)
#     await assert_status(resp, status.HTTP_204_NO_CONTENT)

#     # move project to the root directory
#     url = client.app.router["replace_project_folder"].url_for(
#         folder_id="null", project_id=f"{user_project['uuid']}"
#     )
#     resp = await client.put(url.path)
#     await assert_status(resp, status.HTTP_204_NO_CONTENT)
