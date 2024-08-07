# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
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
    resp = await client.post(
        url.path, json={"name": "My first folder", "description": "Custom description"}
    )
    added_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # list user folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(url.path)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["name"] == "My first folder"
    assert data[0]["description"] == "Custom description"

    # update a folder
    url = client.app.router["replace_folder"].url_for(
        folder_id=f"{added_folder['folderId']}"
    )
    resp = await client.put(
        url.path,
        json={
            "name": "My Second folder",
            "description": "",
        },
    )
    data, _ = await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # list user folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(url.path)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["name"] == "My Second folder"
    assert data[0]["description"] == ""

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
    # wallets_clean_db: AsyncIterator[None],
    # mock_rut_sum_total_available_credits_in_the_wallet: mock.Mock,
):
    assert client.app

    # list user folders
    url = client.app.router["list_folders"].url_for()
    resp = await client.get(url.path)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []

    # create a new folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        url.path, json={"name": "My first folder", "description": "Custom description"}
    )
    root_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # create a subfolder folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        url.path,
        json={
            "name": "My subfolder",
            "description": "Custom subfolder description",
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
    assert data[0]["description"] == "Custom description"

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
            "description": "Custom sub sub folder description",
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
    assert data[0]["description"] == "Custom sub sub folder description"
    assert data[0]["parentFolderId"] == subfolder_folder["folderId"]
