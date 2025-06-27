# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


from copy import deepcopy
from http import HTTPStatus
from unittest import mock

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.workspaces import WorkspaceGet
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_projects import create_project
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def mock_storage_delete_data_folders(mocker: MockerFixture) -> mock.Mock:
    mocker.patch(
        "simcore_service_webserver.dynamic_scheduler.api.list_dynamic_services",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.remove_project_dynamic_services",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.projects._crud_api_delete.director_v2_service.delete_pipeline",
        autospec=True,
    )
    return mocker.patch(
        "simcore_service_webserver.projects._crud_api_delete.delete_data_folders_of_project",
        return_value=None,
    )


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_workspaces_full_workflow_deletion(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
    mock_storage_delete_data_folders: mock.Mock,
):
    assert client.app

    # create a new workspace
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
    added_workspace = WorkspaceGet.model_validate(data)

    # Create project in workspace
    project_data = deepcopy(fake_project)
    project_data["workspace_id"] = f"{added_workspace.workspace_id}"
    first_project = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )
    second_project = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )
    third_project = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )

    # List project in workspace
    url = (
        client.app.router["list_projects"]
        .url_for()
        .with_query({"workspace_id": f"{added_workspace.workspace_id}"})
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 3

    # Create folder in workspace
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "Original user folder",
            "workspaceId": f"{added_workspace.workspace_id}",
        },
    )
    first_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # Create sub folder of previous folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "Second user folder",
            "workspaceId": f"{added_workspace.workspace_id}",
            "parentFolderId": f"{first_folder['folderId']}",
        },
    )
    second_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # Move first project in specific folder in workspace
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{first_folder['folderId']}",
        project_id=f"{first_project['uuid']}",
    )
    resp = await client.put(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Move second project in specific folder in workspace
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{second_folder['folderId']}",
        project_id=f"{second_project['uuid']}",
    )
    resp = await client.put(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # ---------------------
    # TESTING DELETION
    # ---------------------

    # Delete workspace
    url = client.app.router["delete_workspace"].url_for(
        workspace_id=f"{added_workspace.workspace_id}"
    )
    resp = await client.delete(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # ---------------------
    # Assertions

    resp = await client.get(f"/v0/workspaces/{added_workspace.workspace_id}")
    await assert_status(resp, status.HTTP_403_FORBIDDEN)

    resp = await client.get(f"/v0/folders/{first_folder['folderId']}")
    await assert_status(resp, status.HTTP_403_FORBIDDEN)

    resp = await client.get(f"/v0/folders/{second_folder['folderId']}")
    await assert_status(resp, status.HTTP_403_FORBIDDEN)

    resp = await client.get(f"/v0/projects/{first_project['uuid']}")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)

    resp = await client.get(f"/v0/projects/{second_project['uuid']}")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)

    resp = await client.get(f"/v0/projects/{third_project['uuid']}")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)
