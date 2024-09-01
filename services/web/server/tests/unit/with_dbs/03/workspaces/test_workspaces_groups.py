# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterator
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import NewUser, UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_workspaces_groups_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    workspaces_clean_db: AsyncIterator[None],
):
    # create a new workspace
    url = client.app.router["create_workspace"].url_for()
    resp = await client.post(
        f"{url}",
        json={"name": "My first workspace", "description": "Custom description"},
    )
    added_workspace, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # check the default workspace permissions
    url = client.app.router["list_workspace_groups"].url_for(
        workspace_id=f"{added_workspace['workspaceId']}"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["gid"] == logged_user["primary_gid"]
    assert data[0]["read"] == True
    assert data[0]["write"] == True
    assert data[0]["delete"] == True

    async with NewUser(
        app=client.app,
    ) as new_user:
        # We add new user to the workspace
        url = client.app.router["create_workspace_group"].url_for(
            workspace_id=f"{added_workspace['workspaceId']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.post(
            f"{url}", json={"read": True, "write": False, "delete": False}
        )
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)

        # Check the workspace permissions of added user
        url = client.app.router["list_workspace_groups"].url_for(
            workspace_id=f"{added_workspace['workspaceId']}"
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 2
        assert data[1]["gid"] == new_user["primary_gid"]
        assert data[1]["read"] == True
        assert data[1]["write"] == False
        assert data[1]["delete"] == False

        # Update the workspace permissions of the added user
        url = client.app.router["replace_workspace_group"].url_for(
            workspace_id=f"{added_workspace['workspaceId']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.put(
            f"{url}", json={"read": True, "write": True, "delete": False}
        )
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert data["gid"] == new_user["primary_gid"]
        assert data["read"] == True
        assert data["write"] == True
        assert data["delete"] == False

        # List the workspace groups
        url = client.app.router["list_workspace_groups"].url_for(
            workspace_id=f"{added_workspace['workspaceId']}"
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 2
        assert data[1]["gid"] == new_user["primary_gid"]
        assert data[1]["read"] == True
        assert data[1]["write"] == True
        assert data[1]["delete"] == False

        # Delete the workspace group
        url = client.app.router["delete_workspace_group"].url_for(
            workspace_id=f"{added_workspace['workspaceId']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.delete(f"{url}")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        # List the workspace groups
        url = client.app.router["list_workspace_groups"].url_for(
            workspace_id=f"{added_workspace['workspaceId']}"
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 1
        assert data[0]["gid"] == logged_user["primary_gid"]
