# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.workspaces import WorkspaceGet
from models_library.rest_ordering import OrderDirection
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.workspaces._workspaces_handlers import (
    WorkspacesListQueryParams,
)


def test_workspaces_order_query_model_post_validator():

    # on default
    query_params = WorkspacesListQueryParams.parse_obj({})
    assert query_params.order_by
    assert query_params.order_by.field == "modified"
    assert query_params.order_by.direction == OrderDirection.DESC

    # on partial default
    query_params = WorkspacesListQueryParams.parse_obj(
        {"order_by": {"field": "modified_at"}}
    )
    assert query_params.order_by
    assert query_params.order_by.field == "modified"
    assert query_params.order_by.direction == OrderDirection.ASC


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_workspaces_user_role_permissions(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: ExpectedResponse,
):
    assert client.app

    url = client.app.router["list_workspaces"].url_for()
    resp = await client.get(f"{url}")
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
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []

    # CREATE a new workspace
    url = client.app.router["create_workspace"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "My first workspace",
            "description": "Custom description",
            "thumbnail": None,
        },
    )
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    added_workspace = WorkspaceGet.parse_obj(data)

    # LIST user workspaces
    url = client.app.router["list_workspaces"].url_for()
    resp = await client.get(f"{url}")
    data, _, meta, links = await assert_status(
        resp, status.HTTP_200_OK, include_meta=True, include_links=True
    )
    assert len(data) == 1
    assert data[0] == added_workspace.dict()
    assert meta["count"] == 1
    assert links

    # GET a user workspace
    url = client.app.router["get_workspace"].url_for(
        workspace_id=f"{added_workspace.workspace_id}"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["workspaceId"] == added_workspace.workspace_id
    assert data["name"] == "My first workspace"
    assert data["description"] == "Custom description"

    # REPLACE a workspace
    url = client.app.router["replace_workspace"].url_for(
        workspace_id=f"{added_workspace.workspace_id}"
    )
    resp = await client.put(
        f"{url}",
        json={
            "name": "My Second workspace",
            "description": "",
        },
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    replaced_workspace = WorkspaceGet.parse_obj(data)

    # LIST user workspaces
    url = client.app.router["list_workspaces"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0] == replaced_workspace.dict()

    # DELETE a workspace
    url = client.app.router["delete_workspace"].url_for(
        workspace_id=f"{added_workspace.workspace_id}"
    )
    resp = await client.delete(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # LIST user workspaces
    url = client.app.router["list_workspaces"].url_for()
    resp = await client.get(f"{url}")
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
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/6778
