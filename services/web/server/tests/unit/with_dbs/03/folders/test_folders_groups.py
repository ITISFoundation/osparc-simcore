# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.folders import FolderGet
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import NewUser, UserInfoDict
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

    # create a new folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        url.path, json={"name": "Folder A", "description": "Custom description"}
    )
    root_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)
    assert FolderGet.parse_obj(root_folder)

    # get user folder
    url = client.app.router["get_folder"].url_for(
        folder_id=f"{root_folder['folderId']}"
    )
    resp = await client.get(url.path)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data["accessRights"]) == 1

    async with NewUser(
        app=client.app,
    ) as new_user:
        # create
        url = client.app.router["create_folder_group"].url_for(
            folder_id=f"{root_folder['folderId']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.post(
            f"{url}", json={"read": True, "write": False, "delete": False}
        )
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        url = client.app.router["get_folder"].url_for(
            folder_id=f"{root_folder['folderId']}"
        )
        resp = await client.get(url.path)
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data["accessRights"]) == 2
        assert data["accessRights"][f"{new_user['primary_gid']}"] == {
            "read": True,
            "write": False,
            "delete": False,
        }

        # update
        url = client.app.router["replace_folder_group"].url_for(
            folder_id=f"{root_folder['folderId']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.put(
            f"{url}", json={"read": True, "write": True, "delete": False}
        )
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        url = client.app.router["get_folder"].url_for(
            folder_id=f"{root_folder['folderId']}"
        )
        resp = await client.get(url.path)
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data["accessRights"]) == 2
        assert data["accessRights"][f"{new_user['primary_gid']}"] == {
            "read": True,
            "write": True,
            "delete": False,
        }

        # delete
        url = client.app.router["delete_folder_group"].url_for(
            folder_id=f"{root_folder['folderId']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.delete(f"{url}")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        url = client.app.router["get_folder"].url_for(
            folder_id=f"{root_folder['folderId']}"
        )
        resp = await client.get(url.path)
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data["accessRights"]) == 2
        assert data["accessRights"][f"{new_user['primary_gid']}"] == {
            "read": False,
            "write": False,
            "delete": False,
        }

        #### Now we create additional subfolders

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

        # GET sub
        url = client.app.router["get_folder"].url_for(
            folder_id=f"{root_folder['folderId']}"
        )
        resp = await client.get(url.path)
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data["accessRights"]) == 2
        assert data["accessRights"][f"{new_user['primary_gid']}"] == {
            "read": False,
            "write": False,
            "delete": False,
        }

        # GET sub sub
        url = client.app.router["get_folder"].url_for(
            folder_id=f"{root_folder['folderId']}"
        )
        resp = await client.get(url.path)
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data["accessRights"]) == 2
        assert data["accessRights"][f"{new_user['primary_gid']}"] == {
            "read": False,
            "write": False,
            "delete": False,
        }
