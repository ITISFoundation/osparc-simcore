# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


from copy import deepcopy
from http.client import NO_CONTENT

import pytest
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_projects import create_project
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
async def moving_folder_id(
    client: TestClient,
    logged_user: UserInfoDict,
    fake_project: ProjectDict,
) -> str:
    assert client.app
    setup_db(client.app)

    ### Project creation

    # Create 2 projects
    project_data = deepcopy(fake_project)
    first_project = await create_project(
        client.app,
        params_override=project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )
    second_project = await create_project(
        client.app,
        params_override=project_data,
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
    url = client.app.router["move_folder_to_workspace"].url_for(
        folder_id=folder_id,
        workspace_id=workspace_id,
    )
    resp = await client.post(f"{url}")
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


async def test_moving_between_private_and_shared_workspaces(
    client: TestClient,
    logged_user: UserInfoDict,
    fake_project: ProjectDict,
    moving_folder_id: str,
    workspaces_clean_db: None,
):
    assert client.app

    # We will test these scenarios of moving folders:
    # 1. Private workspace -> Shared workspace
    # 2. Shared workspace A -> Shared workspace B
    # 3. Shared workspace A -> Shared workspace A (Corner case - This endpoint is not used like this)
    # 4. Shared workspace -> Private workspace
    # 5. Private workspace -> Private workspace (Corner case - This endpoint is not used like this)

    # create a new workspace
    url = client.app.router["create_workspace"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "A",
            "description": "A",
            "thumbnail": None,
        },
    )
    shared_workspace_A, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # 1. Private workspace -> Shared workspace A
    await _move_folder_to_workspace_and_assert(
        client,
        folder_id=moving_folder_id,
        workspace_id=f"{shared_workspace_A['workspaceId']}",
    )

    # create a new workspace
    url = client.app.router["create_workspace"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "name": "B",
            "description": "B",
            "thumbnail": None,
        },
    )
    shared_workspace_B, _ = await assert_status(resp, status.HTTP_201_CREATED)
    # 2. Shared workspace A -> Shared workspace B
    await _move_folder_to_workspace_and_assert(
        client,
        folder_id=moving_folder_id,
        workspace_id=f"{shared_workspace_B['workspaceId']}",
    )

    # 3. (Corner case) Shared workspace B -> Shared workspace B
    await _move_folder_to_workspace_and_assert(
        client,
        folder_id=moving_folder_id,
        workspace_id=f"{shared_workspace_B['workspaceId']}",
    )

    # 4. Shared workspace -> Private workspace
    await _move_folder_to_workspace_and_assert(
        client, folder_id=moving_folder_id, workspace_id="null"
    )

    # 5. (Corner case) Private workspace -> Private workspace
    await _move_folder_to_workspace_and_assert(
        client, folder_id=moving_folder_id, workspace_id="null"
    )
