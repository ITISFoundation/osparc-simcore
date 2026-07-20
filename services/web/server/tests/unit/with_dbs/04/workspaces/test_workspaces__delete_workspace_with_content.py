# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import dataclasses
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


@dataclasses.dataclass(frozen=True)
class _ProjectDeletionMocks:
    storage_delete_project_data_folders: mock.Mock
    director_v2_delete_pipeline: mock.Mock


@pytest.fixture
def mock_project_deletion_side_effects(mocker: MockerFixture) -> _ProjectDeletionMocks:
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.remove_project_dynamic_services",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.director_v2_service.stop_pipeline",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.director_v2_service.is_pipeline_running",
        autospec=True,
        return_value=False,
    )
    director_v2_delete_pipeline = mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.director_v2_service.delete_pipeline",
        autospec=True,
    )
    storage_delete_project_data_folders = mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.storage_service.delete_project_data_folders",
        return_value=None,
    )
    return _ProjectDeletionMocks(
        storage_delete_project_data_folders=storage_delete_project_data_folders,
        director_v2_delete_pipeline=director_v2_delete_pipeline,
    )


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_workspaces_full_workflow_deletion(
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
    mock_project_deletion_side_effects: _ProjectDeletionMocks,
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
    url = client.app.router["list_projects"].url_for().with_query({"workspace_id": f"{added_workspace.workspace_id}"})
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
    url = client.app.router["delete_workspace"].url_for(workspace_id=f"{added_workspace.workspace_id}")
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


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_workspaces_deletion_cleans_up_project_storage_and_pipeline_data(
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
    mock_project_deletion_side_effects: _ProjectDeletionMocks,
):
    """Regression test for a data-loss bug in ``delete_workspace_with_all_content``.

    That function only marks each root project for trash (relying on the periodic
    garbage-collector to eventually run ``delete_project_as_admin`` and clean up
    storage/pipeline data), then immediately hard-deletes the workspace row. Because
    ``projects.workspace_id`` has ``ON DELETE CASCADE``, Postgres removes the project
    rows in that same step, before the GC ever gets a chance to run. As a result,
    storage (S3) data and pipeline data are never cleaned up for these projects.

    This test currently FAILS (mocks below are never called), demonstrating the bug.
    """
    assert client.app

    # create a new workspace
    url = client.app.router["create_workspace"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "Workspace to be deleted",
            "description": "Custom description",
            "thumbnail": None,
        },
    )
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    added_workspace = WorkspaceGet.model_validate(data)

    # Create projects in workspace
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
    created_projects = [first_project, second_project]

    # ---------------------
    # TESTING DELETION
    # ---------------------

    url = client.app.router["delete_workspace"].url_for(workspace_id=f"{added_workspace.workspace_id}")
    resp = await client.delete(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # ---------------------
    # Assertions

    for project in created_projects:
        resp = await client.get(f"/v0/projects/{project['uuid']}")
        await assert_status(resp, status.HTTP_404_NOT_FOUND)

    # These are the assertions that demonstrate the bug: each project's storage and
    # pipeline data must be cleaned up (once per project) as part of deleting the
    # workspace. Today they are NOT, because the projects are cascade-deleted from the
    # DB before the GC ever gets a chance to run `delete_project_as_admin` on them.
    assert mock_project_deletion_side_effects.storage_delete_project_data_folders.call_count == len(created_projects), (
        "project storage data was not cleaned up (orphaned S3 data bug)"
    )
    assert mock_project_deletion_side_effects.director_v2_delete_pipeline.call_count == len(created_projects), (
        "project pipeline data was not cleaned up (orphaned pipeline data bug)"
    )
