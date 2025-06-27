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
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_projects import create_project
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects import (
    _projects_repository as projects_service_repository,
)
from simcore_service_webserver.projects.models import ProjectDict

_SEARCH_NAME_1 = "Quantum Solutions"
_SEARCH_NAME_2 = "Orion solution"
_SEARCH_NAME_3 = "Skyline solutions"


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_workspaces__list_projects_full_search(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
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
    resp = await client.get(f"{url}")
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
    resp = await client.get(f"{url}")
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
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == project_3["uuid"]
    assert data[0]["workspaceId"] is None
    assert data[0]["folderId"] == root_folder["folderId"]

    # List project with full search (it should return data across all workspaces/folders)
    base_url = client.app.router["list_projects_full_search"].url_for()
    url = base_url.with_query({"text": "solution"})
    resp = await client.get(f"{url}")
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


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test__list_projects_full_search_with_query_parameters(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
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
    resp = await client.get(f"{url}")
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
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == project["uuid"]

    # NOTE: MD: To improve the listing project performance https://github.com/ITISFoundation/osparc-simcore/pull/7475
    # we are not using the tag_ids in the full search (https://github.com/ITISFoundation/osparc-simcore/issues/7478)

    # # Full search with tag_ids
    # base_url = client.app.router["list_projects_full_search"].url_for()
    # url = base_url.with_query({"text": "Orion", "tag_ids": "1,2"})
    # resp = await client.get(f"{url}")
    # data, _ = await assert_status(resp, status.HTTP_200_OK)
    # assert len(data) == 0

    # # Create tag
    # url = client.app.router["create_tag"].url_for()
    # resp = await client.post(
    #     f"{url}", json={"name": "tag1", "description": "description1", "color": "#f00"}
    # )
    # added_tag, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # # Add tag to study
    # url = client.app.router["add_project_tag"].url_for(
    #     project_uuid=project["uuid"], tag_id=str(added_tag.get("id"))
    # )
    # resp = await client.post(f"{url}")
    # data, _ = await assert_status(resp, status.HTTP_200_OK)

    # # Full search with tag_ids
    # base_url = client.app.router["list_projects_full_search"].url_for()
    # url = base_url.with_query({"text": "Orion", "tag_ids": f"{added_tag['id']}"})
    # resp = await client.get(f"{url}")
    # data, _ = await assert_status(resp, status.HTTP_200_OK)
    # assert len(data) == 1
    # assert data[0]["uuid"] == project["uuid"]


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test__list_projects_full_search_with_type_filter(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
):
    """Test the list_projects_full_search endpoint with type query parameter."""
    assert client.app

    # Create a regular user project
    user_project_data = deepcopy(fake_project)
    user_project_data["name"] = "User Project Test"
    user_project_created = await create_project(
        client.app,
        user_project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )

    # Create a template project
    template_project_data = deepcopy(fake_project)
    template_project_data["name"] = "Template Project Test"
    template_project_created = await create_project(
        client.app,
        template_project_data,
        user_id=logged_user["id"],
        product_name="osparc",
        as_template=True,
    )

    base_url = client.app.router["list_projects_full_search"].url_for()

    # Test: Filter by type="user"
    url = base_url.with_query({"text": "Project Test", "type": "user"})
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    user_project_uuids = [p["uuid"] for p in data]
    assert user_project_created["uuid"] in user_project_uuids
    assert template_project_created["uuid"] not in user_project_uuids

    # Test: Filter by type="template"
    url = base_url.with_query({"text": "Project Test", "type": "template"})
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    template_project_uuids = [p["uuid"] for p in data]
    assert user_project_created["uuid"] not in template_project_uuids
    assert template_project_created["uuid"] in template_project_uuids

    # Test: Filter by type="all"
    url = base_url.with_query({"text": "Project Test", "type": "all"})
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    all_project_uuids = [p["uuid"] for p in data]
    assert user_project_created["uuid"] in all_project_uuids
    assert template_project_created["uuid"] in all_project_uuids

    # Test: Default behavior (no type parameter)
    url = base_url.with_query({"text": "Project Test"})
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    default_project_uuids = [p["uuid"] for p in data]
    assert user_project_created["uuid"] in default_project_uuids
    assert template_project_created["uuid"] in default_project_uuids


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test__list_projects_full_search_with_template_type_hypertool_and_tutorial(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
):
    """Test the list_projects_full_search endpoint with template_type hypertool and tutorial."""
    assert client.app

    # Create a hypertool template project
    hypertool_project_data = deepcopy(fake_project)
    hypertool_project_data["name"] = "Hypertool Project Test"
    hypertool_project_created = await create_project(
        client.app,
        hypertool_project_data,
        user_id=logged_user["id"],
        product_name="osparc",
        as_template=True,
    )
    # Patch the hypertool project to set template_type to "HYPERTOOL"
    await projects_service_repository.patch_project(
        client.app,
        project_uuid=hypertool_project_created["uuid"],
        new_partial_project_data={"template_type": "HYPERTOOL"},
    )
    # Create a tutorial template project
    tutorial_project_data = deepcopy(fake_project)
    tutorial_project_data["name"] = "Tutorial Project Test"
    tutorial_project_created = await create_project(
        client.app,
        tutorial_project_data,
        user_id=logged_user["id"],
        product_name="osparc",
        as_template=True,
    )
    # Patch the tutorial project to set template_type to "TUTORIAL"
    await projects_service_repository.patch_project(
        client.app,
        project_uuid=tutorial_project_created["uuid"],
        new_partial_project_data={"template_type": "TUTORIAL"},
    )

    base_url = client.app.router["list_projects_full_search"].url_for()

    # Test: Filter by template_type="hypertool"
    url = base_url.with_query(
        {"text": "Project Test", "type": "template", "template_type": "HYPERTOOL"}
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    hypertool_uuids = [p["uuid"] for p in data]
    assert hypertool_project_created["uuid"] in hypertool_uuids
    assert tutorial_project_created["uuid"] not in hypertool_uuids

    # Test: Filter by template_type="tutorial"
    url = base_url.with_query(
        {"text": "Project Test", "type": "template", "template_type": "TUTORIAL"}
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    tutorial_uuids = [p["uuid"] for p in data]
    assert hypertool_project_created["uuid"] not in tutorial_uuids
    assert tutorial_project_created["uuid"] in tutorial_uuids


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test__list_projects_full_search_with_template_type_regular_and_none(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
):
    """Test the list_projects_full_search endpoint with template_type template and None."""
    assert client.app

    # Create a regular user project
    user_project_data = deepcopy(fake_project)
    user_project_data["name"] = "User Project Test"
    user_project_created = await create_project(
        client.app,
        user_project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )

    # Create a regular template project
    template_project_data = deepcopy(fake_project)
    template_project_data["name"] = "Template Project Test"
    template_project_created = await create_project(
        client.app,
        template_project_data,
        user_id=logged_user["id"],
        product_name="osparc",
        as_template=True,
    )

    # Create a hypertool template project for comparison
    hypertool_project_data = deepcopy(fake_project)
    hypertool_project_data["name"] = "Hypertool Project Test"
    hypertool_project_created = await create_project(
        client.app,
        hypertool_project_data,
        user_id=logged_user["id"],
        product_name="osparc",
        as_template=True,
    )
    # Patch the tutorial project to set template_type to "TUTORIAL"
    await projects_service_repository.patch_project(
        client.app,
        project_uuid=hypertool_project_created["uuid"],
        new_partial_project_data={"template_type": "HYPERTOOL"},
    )

    base_url = client.app.router["list_projects_full_search"].url_for()

    # Test: Filter by template_type="template" --> Default type is "all"
    url = base_url.with_query({"text": "Project Test", "template_type": "TEMPLATE"})
    resp = await client.get(f"{url}")
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Test: Filter by type= template_type="null"
    url = base_url.with_query(
        {"text": "Project Test", "type": "all", "template_type": "null"}
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    none_template_uuids = [p["uuid"] for p in data]
    # NOTE: type "all" takes precedence over template_type "null" (practically is not used)
    assert user_project_created["uuid"] in none_template_uuids
    assert template_project_created["uuid"] in none_template_uuids
    assert hypertool_project_created["uuid"] in none_template_uuids

    # Test: Filter by type="user" & template_type="None"
    url = base_url.with_query(
        {"text": "Project Test", "type": "user", "template_type": "None"}
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    none_template_uuids = [p["uuid"] for p in data]
    assert user_project_created["uuid"] in none_template_uuids
    assert template_project_created["uuid"] not in none_template_uuids
    assert hypertool_project_created["uuid"] not in none_template_uuids
