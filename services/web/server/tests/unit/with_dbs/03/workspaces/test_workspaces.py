# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.workspaces import WorkspaceGet
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_workspaces_user_role_permissions(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: ExpectedResponse,
):
    assert client.app

    url = client.app.router["list_workspaces"].url_for()
    resp = await client.get(url.path)
    await assert_status(resp, expected.ok)


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_workspaces_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    assert client.app

    # list user workspaces
    url = client.app.router["list_workspaces"].url_for()
    resp = await client.get(url.path)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []

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
    assert WorkspaceGet.parse_obj(added_workspace)

    # list user workspaces
    url = client.app.router["list_workspaces"].url_for()
    resp = await client.get(url.path)
    data, _, meta, links = await assert_status(
        resp, status.HTTP_200_OK, include_meta=True, include_links=True
    )
    assert len(data) == 1
    assert data[0]["workspaceId"] == added_workspace["workspaceId"]
    assert data[0]["name"] == "My first workspace"
    assert data[0]["description"] == "Custom description"
    assert meta["count"] == 1
    assert links

    # get a user workspace
    url = client.app.router["get_workspace"].url_for(
        workspace_id=f"{added_workspace['workspaceId']}"
    )
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["workspaceId"] == added_workspace["workspaceId"]
    assert data["name"] == "My first workspace"
    assert data["description"] == "Custom description"

    # update a workspace
    url = client.app.router["replace_workspace"].url_for(
        workspace_id=f"{added_workspace['workspaceId']}"
    )
    resp = await client.put(
        url.path,
        json={
            "name": "My Second workspace",
            "description": "",
        },
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert WorkspaceGet.parse_obj(data)

    # list user workspaces
    url = client.app.router["list_workspaces"].url_for()
    resp = await client.get(url.path)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["name"] == "My Second workspace"
    assert data[0]["description"] == ""

    # delete a workspace
    url = client.app.router["delete_workspace"].url_for(
        workspace_id=f"{added_workspace['workspaceId']}"
    )
    resp = await client.delete(url.path)
    data, _ = await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # list user workspaces
    url = client.app.router["list_workspaces"].url_for()
    resp = await client.get(url.path)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_project_workspace_movement_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    assert client.app

    # NOTE: MD: not yet implemented
