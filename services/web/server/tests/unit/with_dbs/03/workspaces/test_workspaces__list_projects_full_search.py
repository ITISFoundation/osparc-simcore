# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import json
from copy import deepcopy
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_projects import create_project
from servicelib.aiohttp import status
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


_SEARCH_NAME_1 = "Quantum Solutions"
_SEARCH_NAME_2 = "Orion solution"
_SEARCH_NAME_3 = "Skyline solutions"


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_workspaces__list_projects_full_search(
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

    # Create project in shared workspace
    project_data = deepcopy(fake_project)
    project_data["workspace_id"] = f"{added_workspace['workspaceId']}"
    project_data["name"] = _SEARCH_NAME_1
    project_1 = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )

    # List project with full search
    base_url = client.app.router["list_projects_full_search"].url_for()
    url = base_url.with_query({"text": "solution"})
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == project_1["uuid"]
    assert data[0]["workspaceId"] == added_workspace["workspaceId"]
    assert data[0]["folderId"] is None
    assert data[0]["workbench"]
    assert data[0]["accessRights"]

    # Create projects in private workspace
    project_data = deepcopy(fake_project)
    project_data["name"] = _SEARCH_NAME_2
    project_2 = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )

    # List project with full search
    base_url = client.app.router["list_projects_full_search"].url_for()
    url = base_url.with_query({"text": "Orion"})
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == project_2["uuid"]
    assert data[0]["workspaceId"] is None
    assert data[0]["folderId"] is None

    # Create projects in private workspace and move it to a folder
    project_data = deepcopy(fake_project)
    project_data["description"] = _SEARCH_NAME_3
    project_3 = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )

    # create a folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(url.path, json={"name": "My first folder"})
    root_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # add project to the folder
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{root_folder['folderId']}",
        project_id=f"{project_3['uuid']}",
    )
    resp = await client.put(url.path)
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # List project with full search
    base_url = client.app.router["list_projects_full_search"].url_for()
    url = base_url.with_query({"text": "Skyline"})
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == project_3["uuid"]
    assert data[0]["workspaceId"] is None
    assert data[0]["folderId"] == root_folder["folderId"]

    # List project with full search (it should return data across all workspaces/folders)
    base_url = client.app.router["list_projects_full_search"].url_for()
    url = base_url.with_query({"text": "solution"})
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    sorted_data = sorted(data, key=lambda x: x["uuid"])
    assert len(sorted_data) == 3

    assert sorted_data[0]["uuid"] == project_1["uuid"]
    assert sorted_data[0]["workspaceId"] == added_workspace["workspaceId"]
    assert sorted_data[0]["folderId"] is None

    assert sorted_data[1]["uuid"] == project_2["uuid"]
    assert sorted_data[1]["workspaceId"] is None
    assert sorted_data[1]["folderId"] is None

    assert sorted_data[2]["uuid"] == project_3["uuid"]
    assert sorted_data[2]["workspaceId"] is None
    assert sorted_data[2]["folderId"] == root_folder["folderId"]


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test__list_projects_full_search_with_query_parameters(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_api_get_services_for_user_in_product: MockerFixture,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
):
    assert client.app

    # Create projects in private workspace
    project_data = deepcopy(fake_project)
    project_data["name"] = _SEARCH_NAME_2
    project = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )

    # Full search with text
    base_url = client.app.router["list_projects_full_search"].url_for()
    url = base_url.with_query({"text": "Orion"})
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == project["uuid"]

    # Full search with order_by
    base_url = client.app.router["list_projects_full_search"].url_for()
    url = base_url.with_query(
        {
            "text": "Orion",
            "order_by": json.dumps({"field": "uuid", "direction": "desc"}),
        }
    )
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == project["uuid"]

    # Full search with tag_ids
    base_url = client.app.router["list_projects_full_search"].url_for()
    url = base_url.with_query({"text": "Orion", "tag_ids": "1,2"})
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 0

    # Create tag
    url = client.app.router["create_tag"].url_for()
    resp = await client.post(
        f"{url}", json={"name": "tag1", "description": "description1", "color": "#f00"}
    )
    added_tag, _ = await assert_status(resp, expected)

    # Add tag to study
    url = client.app.router["add_project_tag"].url_for(
        project_uuid=project["uuid"], tag_id=str(added_tag.get("id"))
    )
    resp = await client.post(f"{url}")
    data, _ = await assert_status(resp, expected)

    # Full search with tag_ids
    base_url = client.app.router["list_projects_full_search"].url_for()
    url = base_url.with_query({"text": "Orion", "tag_ids": f"{added_tag['id']}"})
    resp = await client.get(url)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == project["uuid"]
