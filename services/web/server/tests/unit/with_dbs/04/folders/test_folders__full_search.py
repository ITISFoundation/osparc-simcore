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
from pytest_simcore.helpers.webserver_login import LoggedUser, UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_folders_user_role_permissions(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: ExpectedResponse,
):
    assert client.app

    url = client.app.router["list_folders_full_search"].url_for()
    resp = await client.get(f"{url}")
    await assert_status(resp, expected.ok)


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_folders_full_search(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    assert client.app

    # list full folder search
    url = client.app.router["list_folders_full_search"].url_for()
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

    # list full folder search
    url = client.app.router["list_folders_full_search"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 2

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

    # list full folder search
    url = client.app.router["list_folders_full_search"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 3

    # list full folder search with specific text
    url = client.app.router["list_folders_full_search"].url_for()
    query_parameters = {"text": "My subfolder"}
    url_with_query = url.with_query(**query_parameters)
    resp = await client.get(f"{url_with_query}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1

    # Create new user
    async with LoggedUser(client) as new_logged_user:
        # list full folder search
        url = client.app.router["list_folders_full_search"].url_for()
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert data == []

        # create a new folder
        url = client.app.router["create_folder"].url_for()
        resp = await client.post(f"{url}", json={"name": "New user folder"})
        new_user_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

        # list full folder search
        url = client.app.router["list_folders_full_search"].url_for()
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 1
