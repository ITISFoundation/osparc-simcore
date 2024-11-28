# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


from copy import deepcopy
from http import HTTPStatus
from http.client import NO_CONTENT

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


# @pytest.mark.parametrize(*standard_role_response(), ids=str)
# async def test_moving_between_workspaces_user_role_permissions(
#     client: TestClient,
#     logged_user: UserInfoDict,
#     user_project: ProjectDict,
#     expected: ExpectedResponse,
#     mock_catalog_api_get_services_for_user_in_product: MockerFixture,
#     fake_project: ProjectDict,
#     workspaces_clean_db: None,
# ):
#     # Move project from workspace to your private workspace
#     base_url = client.app.router["replace_folder_workspace"].url_for(
#         folder_id="1", workspace_id="null"
#     )
#     resp = await client.put(f"{base_url}")
#     await assert_status(resp, expected.no_content)


## Usecases to test:
# 1. Private workspace -> Shared workspace
# 2. Shared workspace -> Shared workspace
# 3. Shared workspace -> Private workspace


async def _setup_test(
    client: TestClient,
    logged_user: UserInfoDict,
    fake_project: ProjectDict,
) -> str:
    assert client.app

    ### Project creation

    # Create 2 projects
    project_data = deepcopy(fake_project)
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

    ### Folder creation

    # Create folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "Original user folder",
        },
    )
    first_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # Create sub folder of previous folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "Second user folder",
            "parentFolderId": f"{first_folder['folderId']}",
        },
    )
    second_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # Create sub sub folder of previous sub folder
    url = client.app.router["create_folder"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "Third user folder",
            "parentFolderId": f"{second_folder['folderId']}",
        },
    )
    third_folder, _ = await assert_status(resp, status.HTTP_201_CREATED)

    ### Move projects to subfolder
    # add first project to the folder
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{second_folder['folderId']}", project_id=f"{first_project['uuid']}"
    )
    resp = await client.put(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)
    # add second project to the folder
    url = client.app.router["replace_project_folder"].url_for(
        folder_id=f"{second_folder['folderId']}", project_id=f"{second_project['uuid']}"
    )
    resp = await client.put(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    ## Double check whether everything is setup OK
    url = (
        client.app.router["list_projects"]
        .url_for()
        .with_query({"folder_id": f"{second_folder['folderId']}"})
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 2

    url = (
        client.app.router["list_projects"]
        .url_for()
        .with_query({"folder_id": f"{first_folder['folderId']}"})
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 0

    url = client.app.router["list_projects"].url_for().with_query({"folder_id": "null"})
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 0

    url = client.app.router["list_folders"].url_for().with_query({"folder_id": "null"})
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1

    url = (
        client.app.router["list_folders"]
        .url_for()
        .with_query({"folder_id": f"{first_folder['folderId']}"})
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1

    return f"{second_folder['folderId']}"


async def _move_folder_to_workspace_and_assert(
    client: TestClient, folder_id: str, workspace_id: str
):
    assert client.app

    # MOVE
    base_url = client.app.router["replace_folder_workspace"].url_for(
        folder_id=folder_id,
        workspace_id=workspace_id,
    )
    resp = await client.put(f"{base_url}")
    await assert_status(resp, NO_CONTENT)

    # ASSERT
    url = (
        client.app.router["list_projects"]
        .url_for()
        .with_query(
            {
                "folder_id": folder_id,
                "workspace_id": workspace_id,
            }
        )
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 2

    url = (
        client.app.router["list_folders"]
        .url_for()
        .with_query(
            {
                "folder_id": folder_id,
                "workspace_id": workspace_id,
            }
        )
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_moving_between_private_and_shared_workspaces(
    client: TestClient,
    logged_user: UserInfoDict,
    # user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_api_get_services_for_user_in_product: MockerFixture,
    fake_project: ProjectDict,
    workspaces_clean_db: None,
):
    assert client.app

    moving_folder_id = await _setup_test(client, logged_user, fake_project)

    # We will test these scenarios of moving folders:
    # 1. Private workspace -> Shared workspace
    # 2. Shared workspace A -> Shared workspace B
    # 3. Shared workspace A -> Shared workspace A (Corner case - This endpoint is not used like this)
    # 4. Shared workspace -> Private workspace
    # 5. Private workspace -> Private workspace (Corner case - This endpoint is not used like this)

    # create a new workspace
    url = client.app.router["create_workspace"].url_for()
    resp = await client.post(
        url.path,
        json={
            "name": "A",
            "description": "A",
            "thumbnail": None,
        },
    )
    added_workspace, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # 1. Private workspace -> Shared workspace A
    await _move_folder_to_workspace_and_assert(
        client,
        folder_id=moving_folder_id,
        workspace_id=f"{added_workspace['workspaceId']}",
    )

    # create a new workspace
    url = client.app.router["create_workspace"].url_for()
    resp = await client.post(
        url.path,
        json={
            "name": "B",
            "description": "B",
            "thumbnail": None,
        },
    )
    second_workspace, _ = await assert_status(resp, status.HTTP_201_CREATED)
    # 2. Shared workspace A -> Shared workspace B
    await _move_folder_to_workspace_and_assert(
        client,
        folder_id=moving_folder_id,
        workspace_id=f"{second_workspace['workspaceId']}",
    )

    # 3. (Corner case) Shared workspace A -> Shared workspace A
    await _move_folder_to_workspace_and_assert(
        client,
        folder_id=moving_folder_id,
        workspace_id=f"{second_workspace['workspaceId']}",
    )

    # 4. Shared workspace -> Private workspace
    await _move_folder_to_workspace_and_assert(
        client, folder_id=moving_folder_id, workspace_id="null"
    )

    # 5. (Corner case) Private workspace -> Private workspace
    await _move_folder_to_workspace_and_assert(
        client, folder_id=moving_folder_id, workspace_id="null"
    )
