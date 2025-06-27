# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from collections.abc import AsyncIterable
from copy import deepcopy
from unittest.mock import MagicMock
from uuid import UUID

import arrow
import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.folders_v2 import FolderGet
from models_library.api_schemas_webserver.projects import ProjectGet, ProjectListItem
from models_library.api_schemas_webserver.workspaces import WorkspaceGet
from models_library.rest_pagination import Page
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_projects import create_project
from servicelib.aiohttp import status
from simcore_postgres_database.models.folders_v2 import folders_v2
from simcore_postgres_database.models.projects import projects
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects._groups_service import ProjectGroupGet
from simcore_service_webserver.projects.models import ProjectDict
from tenacity import AsyncRetrying, stop_after_attempt, wait_fixed
from yarl import URL


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/pull/6579"
)
@pytest.mark.parametrize("force", [False, True])
@pytest.mark.parametrize("is_project_running", [False, True])
async def test_trash_projects(  # noqa: PLR0915
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mocked_catalog: None,
    mocked_director_v2: None,
    mocker: MockerFixture,
    force: bool,
    is_project_running: bool,
):
    assert client.app

    # this test should emulate NO errors stopping services
    mock_remove_dynamic_services = mocker.patch(
        "simcore_service_webserver.projects._trash_service._projects_service_delete._projects_service.remove_project_dynamic_services",
        autospec=True,
    )
    mock_stop_pipeline = mocker.patch(
        "simcore_service_webserver.projects._trash_service._projects_service_delete.director_v2_service.stop_pipeline",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.projects._trash_service.director_v2_service.is_pipeline_running",
        return_value=is_project_running,
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.projects._trash_service.dynamic_scheduler_service.list_dynamic_services",
        return_value=[mocker.MagicMock()] if is_project_running else [],
        autospec=True,
    )

    project_uuid = UUID(user_project["uuid"])

    url = client.app.router["list_projects"].url_for()
    assert f"{url}" == "/v0/projects"

    # ---------------------------------------------------------------------

    # LIST NOT trashed
    resp = await client.get("/v0/projects")
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[ProjectListItem].model_validate(await resp.json())
    assert page.meta.total == 1

    got = page.data[0]
    assert got.uuid == project_uuid
    assert got.trashed_at is None

    # LIST trashed
    resp = await client.get("/v0/projects", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[ProjectListItem].model_validate(await resp.json())
    assert page.meta.total == 0

    # TRASH
    trashing_at = arrow.utcnow().datetime
    resp = await client.post(
        f"/v0/projects/{project_uuid}:trash", params={"force": f"{force}"}
    )
    _, error = await assert_status(
        resp,
        (
            status.HTTP_409_CONFLICT
            if (is_project_running and not force)
            else status.HTTP_204_NO_CONTENT
        ),
    )

    could_not_trash = is_project_running and not force

    if could_not_trash:
        assert "Current study is in use" in error["message"]

    # GET
    resp = await client.get(f"/v0/projects/{project_uuid}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = ProjectGet.model_validate(data)
    assert got.uuid == project_uuid

    if could_not_trash:
        assert got.trashed_at is None
    else:
        assert got.trashed_at
        assert trashing_at < got.trashed_at
        assert got.trashed_at < arrow.utcnow().datetime
        assert got.trashed_by == logged_user["primary_gid"]

    # LIST trashed
    resp = await client.get("/v0/projects", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[ProjectListItem].model_validate(await resp.json())
    if could_not_trash:
        assert page.meta.total == 0
    else:
        assert page.meta.total == 1
        assert page.data[0].uuid == project_uuid

        # UNTRASH
        resp = await client.post(f"/v0/projects/{project_uuid}:untrash")
        data, _ = await assert_status(resp, status.HTTP_204_NO_CONTENT)

        # GET
        resp = await client.get(f"/v0/projects/{project_uuid}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        got = ProjectGet.model_validate(data)

        assert got.uuid == project_uuid
        assert got.trashed_at is None

    if is_project_running and force:
        # checks fire&forget calls
        await asyncio.sleep(0.1)
        mock_stop_pipeline.assert_awaited()
        mock_remove_dynamic_services.assert_awaited()


async def test_trash_projects_shared_among_users(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    other_user: UserInfoDict,
    mocked_catalog: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
):
    assert client.app

    project_uuid = UUID(user_project["uuid"])

    # GET project
    url = client.app.router["get_project"].url_for(project_id=f"{project_uuid}")
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    project = ProjectGet.model_validate(data)
    assert project.uuid == project_uuid
    assert project.prj_owner == logged_user["email"]

    # SHARE PROJECT with other-user
    url = client.app.router["create_project_group"].url_for(
        project_id=f"{project_uuid}", group_id=f"{other_user['primary_gid']}"
    )
    resp = await client.post(
        f"{url}",
        json={"read": True, "write": True, "delete": False},
    )
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)

    project_group = ProjectGroupGet.model_validate(data)
    assert project_group.gid == other_user["primary_gid"]
    assert project_group.read is True
    assert project_group.write is True
    assert project_group.delete is False

    # TRASH project
    trashing_at = arrow.utcnow().datetime
    resp = await client.post(
        f"/v0/projects/{project_uuid}:trash", params={"force": "true"}
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # LIST trashed of logged_user
    resp = await client.get("/v0/projects", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[ProjectListItem].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].uuid == project_uuid
    assert page.data[0].trashed_at
    assert trashing_at < page.data[0].trashed_at
    assert page.data[0].trashed_by == logged_user["primary_gid"]

    # Swith USER: LOGOUT
    url = client.app.router["auth_logout"].url_for()
    resp = await client.post(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)

    url = client.app.router["auth_login"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "email": other_user["email"],
            "password": other_user["raw_password"],
        },
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    # LIST trashed of another_user
    resp = await client.get("/v0/projects", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[ProjectListItem].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].uuid == project_uuid
    assert page.data[0].trashed_at
    assert trashing_at < page.data[0].trashed_at
    assert page.data[0].trashed_by == logged_user["primary_gid"]


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/pull/6642"
)
async def test_trash_single_folder(client: TestClient, logged_user: UserInfoDict):

    assert client.app

    # CREATE a folder
    resp = await client.post("/v0/folders", json={"name": "My first folder"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    folder = FolderGet.model_validate(data)

    # ---------------------------------------------------------------------

    # LIST NOT trashed
    resp = await client.get("/v0/folders")
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 1

    assert page.data[0] == folder

    # LIST trashed
    resp = await client.get("/v0/folders", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 0

    # TRASH
    assert client.app.router["trash_folder"].url_for(folder_id="folder_id") == URL(
        "/v0/folders/folder_id:trash"
    )

    trashing_at = arrow.utcnow().datetime
    resp = await client.post(f"/v0/folders/{folder.folder_id}:trash")
    await assert_status(
        resp,
        status.HTTP_204_NO_CONTENT,
    )

    # GET
    resp = await client.get(f"/v0/folders/{folder.folder_id}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = FolderGet.model_validate(data)
    assert got.folder_id == folder.folder_id

    assert got.trashed_at
    assert trashing_at < got.trashed_at
    assert got.trashed_at < arrow.utcnow().datetime
    assert got.trashed_by == logged_user["primary_gid"]
    assert got.owner == logged_user["primary_gid"]

    # LIST trashed
    resp = await client.get("/v0/folders", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[FolderGet].model_validate(await resp.json())

    assert page.meta.total == 1
    assert page.data[0].folder_id == folder.folder_id

    # UNTRASH
    assert client.app.router["untrash_folder"].url_for(folder_id="folder_id") == URL(
        "/v0/folders/folder_id:untrash"
    )

    resp = await client.post(f"/v0/folders/{folder.folder_id}:untrash")
    data, _ = await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # GET
    resp = await client.get(f"/v0/folders/{folder.folder_id}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = FolderGet.model_validate(data)

    assert got.folder_id == folder.folder_id
    assert got.trashed_at is None


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/pull/6642"
)
async def test_trash_folder_with_content(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mocked_catalog: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
):
    assert client.app
    project_uuid = UUID(user_project["uuid"])

    # CREATE a folder
    resp = await client.post("/v0/folders", json={"name": "My first folder"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    folder = FolderGet.model_validate(data)
    assert folder.trashed_at is None

    # CREATE a SUB-folder
    resp = await client.post(
        "/v0/folders",
        json={"name": "My subfolder 1", "parentFolderId": folder.folder_id},
    )
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    subfolder = FolderGet.model_validate(data)

    # MOVE project to SUB-folder
    resp = await client.put(
        f"/v0/projects/{project_uuid}/folders/{subfolder.folder_id}"
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # CHECK created
    resp = await client.get("/v0/folders")
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0] == folder

    resp = await client.get("/v0/folders", params={"folder_id": f"{folder.folder_id}"})
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0] == subfolder

    resp = await client.get(
        "/v0/projects", params={"folder_id": f"{subfolder.folder_id}"}
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[ProjectListItem].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].uuid == project_uuid
    assert page.data[0].folder_id == subfolder.folder_id

    # ---------------------------------------------------------------------

    # TRASH folder
    resp = await client.post(f"/v0/folders/{folder.folder_id}:trash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # ONLY folder listed in trash. The rest is not listed anymore since they are implicitly trashed!
    resp = await client.get("/v0/folders", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].trashed_at is not None
    assert page.data[0].folder_id == folder.folder_id

    resp = await client.get(
        "/v0/folders",
        params={"filters": '{"trashed": true}', "folder_id": f"{folder.folder_id}"},
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 0

    resp = await client.get(
        "/v0/projects",
        params={"filters": '{"trashed": true}', "folder_id": f"{subfolder.folder_id}"},
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[ProjectListItem].model_validate(await resp.json())
    assert page.meta.total == 0

    # CHECK marked as trashed
    resp = await client.get(f"/v0/folders/{folder.folder_id}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = FolderGet.model_validate(data)
    assert got.trashed_at is not None
    assert got.trashed_by == logged_user["primary_gid"]

    resp = await client.get(f"/v0/folders/{subfolder.folder_id}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = FolderGet.model_validate(data)
    assert got.trashed_at is not None
    assert got.trashed_by == logged_user["primary_gid"]

    resp = await client.get(f"/v0/projects/{project_uuid}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = ProjectGet.model_validate(data)
    assert got.trashed_at is not None
    assert got.trashed_by == logged_user["primary_gid"]

    # UNTRASH folder
    resp = await client.post(f"/v0/folders/{folder.folder_id}:untrash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # NO folders listed in trash.
    resp = await client.get("/v0/folders", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 0

    resp = await client.get(
        "/v0/folders",
        params={"filters": '{"trashed": true}', "folder_id": f"{folder.folder_id}"},
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 0

    resp = await client.get(
        "/v0/projects",
        params={"filters": '{"trashed": true}', "folder_id": f"{subfolder.folder_id}"},
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[ProjectListItem].model_validate(await resp.json())
    assert page.meta.total == 0

    # CHECK marked as trashed
    resp = await client.get(f"/v0/folders/{folder.folder_id}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = FolderGet.model_validate(data)
    assert got.trashed_at is None

    resp = await client.get(f"/v0/folders/{subfolder.folder_id}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = FolderGet.model_validate(data)
    assert got.trashed_at is None

    resp = await client.get(f"/v0/projects/{project_uuid}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = ProjectGet.model_validate(data)
    assert got.trashed_at is None


@pytest.fixture
async def workspace(
    client: TestClient, logged_user: UserInfoDict
) -> AsyncIterable[WorkspaceGet]:

    # CREATE a workspace
    resp = await client.post("/v0/workspaces", json={"name": "My first workspace"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    wks = WorkspaceGet.model_validate(data)

    yield wks

    # DELETE a workspace
    resp = await client.delete(f"/v0/workspaces/{wks.workspace_id}")
    data, _ = await assert_status(resp, status.HTTP_204_NO_CONTENT)


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/pull/6690"
)
async def test_trash_empty_workspace(
    client: TestClient,
    logged_user: UserInfoDict,
    workspace: WorkspaceGet,
    mocked_catalog: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
):
    assert client.app

    assert workspace.trashed_at is None
    assert workspace.trashed_by is None

    # LIST NOT trashed (default)
    resp = await client.get("/v0/workspaces")
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0] == workspace

    # LIST trashed
    resp = await client.get("/v0/workspaces", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].model_validate(await resp.json())
    assert page.meta.total == 0

    # -------------

    _exclude_attrs = {"trashed_by", "trashed_at", "modified_at"}

    # TRASH
    trashing_at = arrow.utcnow().datetime
    resp = await client.post(
        f"/v0/workspaces/{workspace.workspace_id}:trash"  # <-- TESTING TRASHING
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # LIST NOT trashed (default)
    resp = await client.get("/v0/workspaces")
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].model_validate(await resp.json())
    assert page.meta.total == 0

    # LIST trashed
    resp = await client.get("/v0/workspaces", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].model_dump(exclude=_exclude_attrs) == workspace.model_dump(
        exclude=_exclude_attrs
    )
    assert page.data[0].trashed_at is not None
    assert trashing_at < page.data[0].trashed_at
    assert page.data[0].trashed_by == logged_user["primary_gid"]

    # --------

    # UN_TRASH
    resp = await client.post(f"/v0/workspaces/{workspace.workspace_id}:untrash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # LIST NOT trashed (default)
    resp = await client.get("/v0/workspaces")
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].model_dump(exclude=_exclude_attrs) == workspace.model_dump(
        exclude=_exclude_attrs
    )

    assert page.data[0].trashed_at is None
    assert page.data[0].trashed_by is None

    # LIST trashed
    resp = await client.get("/v0/workspaces", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].model_validate(await resp.json())
    assert page.meta.total == 0


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/issues/7034"
)
async def test_trash_workspace(
    client: TestClient,
    logged_user: UserInfoDict,
    workspace: WorkspaceGet,
    user_project: ProjectDict,
    fake_project: ProjectDict,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    postgres_db: sa.engine.Engine,
):
    assert client.app

    assert workspace.trashed_at is None
    assert workspace.trashed_by is None

    # LIST NOT trashed (default)
    resp = await client.get("/v0/workspaces")
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0] == workspace

    # LIST trashed
    resp = await client.get("/v0/workspaces", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].model_validate(await resp.json())
    assert page.meta.total == 0

    # -------------
    # add folders and projects to the workspace

    # CREATE a project **in workspace**
    project_data = deepcopy(fake_project)
    project_data["workspace_id"] = f"{workspace.workspace_id}"
    created_project = await create_project(
        client.app,
        project_data,
        user_id=logged_user["id"],
        product_name="osparc",
    )

    # CREATE a folder in workspace
    resp = await client.post(
        "/v0/folders",
        json={
            "name": "Folder",
            # "workspaceId": f"{workspace.workspace_id}",
        },
    )
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    folder = FolderGet.model_validate(data)

    # CREATE a SUB-folder
    resp = await client.post(
        "/v0/folders",
        json={
            "name": "SubFolder1",
            "parentFolderId": folder.folder_id,
            # "workspaceId": f"{workspace.workspace_id}",
        },
    )
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    subfolder = FolderGet.model_validate(data)

    # MOVE project to SUB-folder
    project_uuid = UUID(user_project["uuid"])
    resp = await client.put(
        f"/v0/projects/{project_uuid}/folders/{subfolder.folder_id}"
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # MOVE root folder with content to workspace
    url = client.app.router["move_folder_to_workspace"].url_for(
        folder_id=f"{folder.folder_id}",
        workspace_id=f"{workspace.workspace_id}",
    )
    resp = await client.post(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # -------------
    # list folders and projects in workspace

    # LIST projects in workspace
    url = (
        client.app.router["list_projects"]
        .url_for()
        .with_query({"workspace_id": f"{workspace.workspace_id}"})
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1

    # LIST folders in workspace
    url = (
        client.app.router["list_folders"]
        .url_for()
        .with_query({"workspace_id": f"{workspace.workspace_id}", "folder_id": "null"})
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1

    # LIST FOLDERS in workspace
    url = (
        client.app.router["list_folders"]
        .url_for()
        .with_query({"workspace_id": f"{workspace.workspace_id}", "folder_id": "null"})
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1

    # LIST FOLDERS in subfolder of workspace
    url = (
        client.app.router["list_folders"]
        .url_for()
        .with_query(
            {
                "workspace_id": f"{workspace.workspace_id}",
                "folder_id": f"{folder.folder_id}",
            }
        )
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1

    # LIST PROJECTS in subfolder of workspace
    url = (
        client.app.router["list_projects"]
        .url_for()
        .with_query(
            {
                "workspace_id": f"{workspace.workspace_id}",
                "folder_id": f"{subfolder.folder_id}",
            }
        )
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1

    # -------------

    _exclude_attrs = {"trashed_by", "trashed_at", "modified_at"}

    # TRASH
    trashing_at = arrow.utcnow().datetime
    resp = await client.post(
        f"/v0/workspaces/{workspace.workspace_id}:trash"  # <-- TESTING TRASHING
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # LIST NOT trashed (default)
    resp = await client.get("/v0/workspaces")
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].model_validate(await resp.json())
    assert page.meta.total == 0

    # LIST trashed
    resp = await client.get("/v0/workspaces", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].model_dump(exclude=_exclude_attrs) == workspace.model_dump(
        exclude=_exclude_attrs
    )
    assert page.data[0].trashed_at is not None
    assert trashing_at < page.data[0].trashed_at
    assert page.data[0].trashed_by == logged_user["primary_gid"]

    # Check additional state in the DB
    with postgres_db.connect() as conn:
        # 1. Check that both projects were marked as trashed implicitly
        trashed_projects = conn.execute(
            projects.select().where(
                projects.c.workspace_id == workspace.workspace_id,
                projects.c.trashed.isnot(None),
            )
        )
        trashed_projects = trashed_projects.fetchall()
        assert len(trashed_projects) == 2  # Assuming two projects are expected
        for project in trashed_projects:
            assert project.trashed is not None
            assert project.trashed_by == logged_user["id"]
            assert project.trashed_explicitly is False

        # 2. Check that both folders were marked as trashed implicitly
        trashed_folders = conn.execute(
            folders_v2.select().where(
                folders_v2.c.workspace_id == workspace.workspace_id,
                folders_v2.c.trashed.isnot(None),
            )
        )
        trashed_folders = trashed_folders.fetchall()
        assert len(trashed_folders) == 2  # Assuming two folders are expected
        for folder in trashed_folders:
            assert folder.trashed is not None
            assert folder.trashed_by == logged_user["id"]
            assert folder.trashed_explicitly is False

    # --------

    # UN_TRASH
    resp = await client.post(f"/v0/workspaces/{workspace.workspace_id}:untrash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # LIST NOT trashed (default)
    resp = await client.get("/v0/workspaces")
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].model_dump(exclude=_exclude_attrs) == workspace.model_dump(
        exclude=_exclude_attrs
    )

    assert page.data[0].trashed_at is None
    assert page.data[0].trashed_by is None

    # LIST trashed
    resp = await client.get("/v0/workspaces", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].model_validate(await resp.json())
    assert page.meta.total == 0

    # Check additional state in the DB
    with postgres_db.connect() as conn:
        # 1. Check that both projects were marked as trashed implicitly
        trashed_projects = conn.execute(
            projects.select().where(projects.c.workspace_id == workspace.workspace_id)
        )
        trashed_projects = trashed_projects.fetchall()
        assert len(trashed_projects) == 2  # Assuming two projects are expected
        for project in trashed_projects:
            assert project.trashed is None
            assert project.trashed_by is None
            assert project.trashed_explicitly is False

        # 2. Check that both folders were marked as trashed implicitly
        trashed_folders = conn.execute(
            folders_v2.select().where(
                folders_v2.c.workspace_id == workspace.workspace_id
            )
        )
        trashed_folders = trashed_folders.fetchall()
        assert len(trashed_folders) == 2  # Assuming two folders are expected
        for folder in trashed_folders:
            assert folder.trashed is None
            assert folder.trashed_by is None
            assert folder.trashed_explicitly is False


async def test_trash_subfolder(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mocked_dynamic_services_interface: dict[str, MagicMock],
):
    assert client.app

    # setup --------------------------------
    #
    # - /Folder
    #    - /SubFolder

    # CREATE a folder
    resp = await client.post("/v0/folders", json={"name": "Folder"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    folder = FolderGet.model_validate(data)

    # CREATE a SUB-folder
    resp = await client.post(
        "/v0/folders",
        json={"name": "SubFolder1", "parentFolderId": folder.folder_id},
    )
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    subfolder = FolderGet.model_validate(data)

    # -------------------------------------

    # TRASH subfolder
    resp = await client.post(f"/v0/folders/{subfolder.folder_id}:trash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # LIST BIN (i.e. use full-depth search)
    url = client.app.router["list_folders_full_search"].url_for()
    assert f"{url}" == "/v0/folders:search"

    resp = await client.get(
        "/v0/folders:search", params={"filters": '{"trashed": true}'}
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].folder_id == subfolder.folder_id

    # LIST (NOT full-depth)
    resp = await client.get(
        "/v0/folders",
        params={"filters": '{"trashed": true}'},
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 0

    resp = await client.get(
        "/v0/folders",
        params={"filters": '{"trashed": true}', "folder_id": f"{folder.folder_id}"},
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["folderId"] == subfolder.folder_id

    # UNTRASH
    resp = await client.post(f"/v0/folders/{subfolder.folder_id}:untrash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # check not in the bin
    resp = await client.get(
        "/v0/folders:search", params={"filters": '{"trashed": true}'}
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 0

    # check "back in place"
    resp = await client.get(
        "/v0/folders:search", params={"filters": '{"trashed": false}'}
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 2

    resp = await client.get(
        "/v0/folders",
        params={"filters": '{"trashed": false}', "folder_id": f"{folder.folder_id}"},
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["folderId"] == subfolder.folder_id

    expected = data
    resp = await client.get(
        "/v0/folders",
        params={"folder_id": f"{folder.folder_id}"},
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == expected


async def test_trash_project_in_subfolder(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mocked_dynamic_services_interface: dict[str, MagicMock],
):
    assert client.app

    # setup --------------------------------
    #
    # - /Folder
    #    - /SubFolder
    #       - user_project <-- NOTE: this is a project!
    #

    # CREATE a folder
    resp = await client.post("/v0/folders", json={"name": "Folder"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    folder = FolderGet.model_validate(data)

    # CREATE a SUB-folder
    resp = await client.post(
        "/v0/folders",
        json={"name": "SubFolder1", "parentFolderId": folder.folder_id},
    )
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    subfolder = FolderGet.model_validate(data)

    # MOVE project to SUB-folder
    project_uuid = UUID(user_project["uuid"])
    resp = await client.put(
        f"/v0/projects/{project_uuid}/folders/{subfolder.folder_id}"
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)
    # -------------------------------------

    # TRASH project
    resp = await client.post(f"/v0/projects/{project_uuid}:trash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # LIST BIN (i.e. use full-depth search)
    url = client.app.router["list_projects_full_search"].url_for()
    assert f"{url}" == "/v0/projects:search"

    resp = await client.get(
        "/v0/projects:search", params={"filters": '{"trashed": true}', "type": "user"}
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[ProjectGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].folder_id == subfolder.folder_id

    # LIST (NOT full-depth)
    resp = await client.get(
        "/v0/projects",
        params={"filters": '{"trashed": true}'},
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 0

    resp = await client.get(
        "/v0/projects",
        params={"filters": '{"trashed": true}', "folder_id": f"{subfolder.folder_id}"},
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["uuid"] == f"{project_uuid}"

    # UNTRASH
    resp = await client.post(f"/v0/projects/{project_uuid}:untrash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    resp = await client.get(
        "/v0/projects:search", params={"filters": '{"trashed": true}', "type": "user"}
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[ProjectGet].model_validate(await resp.json())
    assert page.meta.total == 0

    resp = await client.get(
        "/v0/projects:search", params={"filters": '{"trashed": false}', "type": "user"}
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[ProjectGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].uuid == project_uuid


async def test_trash_project_explitictly_and_empty_trash_bin(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mocked_director_v2: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    mocked_storage: None,
):
    assert client.app

    project_uuid = UUID(user_project["uuid"])

    # TRASH project
    trashing_at = arrow.utcnow().datetime
    resp = await client.post(
        f"/v0/projects/{project_uuid}:trash", params={"force": "true"}
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # LIST trashed projects
    resp = await client.get(
        "/v0/projects", params={"filters": '{"trashed": true}', "type": "user"}
    )
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[ProjectListItem].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].uuid == project_uuid

    # GET trashed project
    resp = await client.get(f"/v0/projects/{project_uuid}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = ProjectGet.model_validate(data)
    assert got.uuid == project_uuid
    assert got.trashed_at is not None
    assert trashing_at < got.trashed_at < arrow.utcnow().datetime

    # force EMPTY trash
    resp = await client.post("/v0/trash:empty")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # waits for deletion
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3), wait=wait_fixed(1), reraise=True
    ):
        with attempt:
            # LIST trashed projects again
            resp = await client.get(
                "/v0/projects", params={"filters": '{"trashed": true}'}
            )
            await assert_status(resp, status.HTTP_200_OK)
            page = Page[ProjectListItem].model_validate(await resp.json())
            assert page.meta.total == 0

    # GET trahsed project
    resp = await client.get(f"/v0/projects/{project_uuid}")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)


async def test_trash_folder_with_subfolder_and_project_and_empty_bin(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mocked_director_v2: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    mocked_storage: None,
):
    assert client.app

    # CREATE a folder
    resp = await client.post("/v0/folders", json={"name": "Parent Folder"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    parent_folder = FolderGet.model_validate(data)

    # CREATE a subfolder
    resp = await client.post(
        "/v0/folders",
        json={"name": "Sub Folder", "parentFolderId": parent_folder.folder_id},
    )
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    sub_folder = FolderGet.model_validate(data)

    # MOVE project to subfolder
    project_uuid = UUID(user_project["uuid"])
    resp = await client.put(
        f"/v0/projects/{project_uuid}/folders/{sub_folder.folder_id}"
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # TRASH the parent folder
    resp = await client.post(f"/v0/folders/{parent_folder.folder_id}:trash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # CHECK BIN
    # - LIST trashed folders as shown in the bin (will show only explicilty)
    resp = await client.get(
        "/v0/folders:search", params={"filters": '{"trashed": true}'}
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].folder_id == parent_folder.folder_id

    # - LIST trashed projects (will show only explicit!)
    resp = await client.get(
        "/v0/projects:search", params={"filters": '{"trashed": true}', "type": "user"}
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[ProjectListItem].model_validate(await resp.json())
    assert page.meta.total == 0

    # CHECK items
    # - GET trashed parent folder (explicit)
    resp = await client.get(f"/v0/folders/{parent_folder.folder_id}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = FolderGet.model_validate(data)
    assert got.trashed_at is not None
    assert got.trashed_by == logged_user["primary_gid"]

    # - GET trashed subfolder (implicit)
    resp = await client.get(f"/v0/folders/{sub_folder.folder_id}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = FolderGet.model_validate(data)
    assert got.trashed_at is not None
    assert got.trashed_by == logged_user["primary_gid"]

    # GET trashed project (implicit)
    resp = await client.get(f"/v0/projects/{project_uuid}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = ProjectGet.model_validate(data)
    assert got.trashed_at is not None
    assert got.trashed_by == logged_user["primary_gid"]

    # EMPTY trash
    resp = await client.post("/v0/trash:empty")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # waits for deletion
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3), wait=wait_fixed(1), reraise=True
    ):
        with attempt:
            # GET trashed parent folder
            resp = await client.get(f"/v0/folders/{parent_folder.folder_id}")
            await assert_status(resp, status.HTTP_403_FORBIDDEN)

            # GET trashed subfolder
            resp = await client.get(f"/v0/folders/{sub_folder.folder_id}")
            await assert_status(resp, status.HTTP_403_FORBIDDEN)

            # GET trashed project
            resp = await client.get(f"/v0/projects/{project_uuid}")
            await assert_status(resp, status.HTTP_404_NOT_FOUND)

    # CHECK BIN
    # LIST trashed (will show only explicit)
    resp = await client.get(
        "/v0/folders:search", params={"filters": '{"trashed": true}'}
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 0

    # - LIST trashed projects (will show only explicit!)
    resp = await client.get(
        "/v0/projects:search", params={"filters": '{"trashed": true}', "type": "user"}
    )
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[ProjectListItem].model_validate(await resp.json())
    assert page.meta.total == 0
