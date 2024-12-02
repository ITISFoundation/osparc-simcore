# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from collections.abc import AsyncIterable, Callable
from uuid import UUID

import arrow
import pytest
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from models_library.api_schemas_webserver.folders_v2 import FolderGet
from models_library.api_schemas_webserver.projects import ProjectGet, ProjectListItem
from models_library.api_schemas_webserver.workspaces import WorkspaceGet
from models_library.rest_pagination import Page
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict
from yarl import URL


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch, {"WEBSERVER_DEV_FEATURES_ENABLED": "1"}
    )


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
def mocked_catalog(
    user_project: ProjectDict,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
):
    catalog_subsystem_mock([user_project])


@pytest.fixture
def mocked_director_v2(director_v2_service_mock: aioresponses):
    ...


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

    # this test should have no errors stopping services
    mock_remove_dynamic_services = mocker.patch(
        "simcore_service_webserver.projects._trash_api.projects_api.remove_project_dynamic_services",
        autospec=True,
    )
    mock_stop_pipeline = mocker.patch(
        "simcore_service_webserver.projects._trash_api.director_v2_api.stop_pipeline",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.projects._trash_api.director_v2_api.is_pipeline_running",
        return_value=is_project_running,
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.projects._trash_api.director_v2_api.list_dynamic_services",
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
        status.HTTP_409_CONFLICT
        if (is_project_running and not force)
        else status.HTTP_204_NO_CONTENT,
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
    mocked_director_v2: None,
):
    assert client.app
    project_uuid = UUID(user_project["uuid"])

    # CREATE a folder
    resp = await client.post("/v0/folders", json={"name": "My first folder"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    folder = FolderGet.model_validate(data)

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

    # ONLY folder listed in trash. The rest is not listed anymore!
    resp = await client.get("/v0/folders", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)
    page = Page[FolderGet].model_validate(await resp.json())
    assert page.meta.total == 1
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

    resp = await client.get(f"/v0/folders/{subfolder.folder_id}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = FolderGet.model_validate(data)
    assert got.trashed_at is not None

    resp = await client.get(f"/v0/projects/{project_uuid}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = ProjectGet.model_validate(data)
    assert got.trashed_at is not None

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
    workspace = WorkspaceGet.parse_obj(data)

    yield workspace

    # DELETE a workspace
    resp = await client.delete(f"/v0/workspaces/{workspace.workspace_id}")
    data, _ = await assert_status(resp, status.HTTP_204_NO_CONTENT)


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/pull/6690"
)
async def test_trash_empty_workspace(
    client: TestClient, logged_user: UserInfoDict, workspace: WorkspaceGet
):
    assert client.app

    assert workspace.trashed_at is None
    assert workspace.trashed_by is None

    # LIST NOT trashed (default)
    resp = await client.get("/v0/workspaces")
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].parse_obj(await resp.json())
    assert page.meta.total == 1
    assert page.data[0] == workspace

    # LIST trashed
    resp = await client.get("/v0/workspaces", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].parse_obj(await resp.json())
    assert page.meta.total == 0

    # -------------

    _exclude_attrs = {"trashed_by", "trashed_at", "modified_at"}

    # TRASH
    before_trash = arrow.utcnow().datetime
    resp = await client.post(f"/v0/workspaces/{workspace.workspace_id}:trash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # LIST NOT trashed (default)
    resp = await client.get("/v0/workspaces")
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].parse_obj(await resp.json())
    assert page.meta.total == 0

    # LIST trashed
    resp = await client.get("/v0/workspaces", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].parse_obj(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].dict(exclude=_exclude_attrs) == workspace.dict(
        exclude=_exclude_attrs
    )
    assert page.data[0].trashed_at is not None
    assert before_trash < page.data[0].trashed_at
    assert page.data[0].trashed_by == logged_user["id"]

    # --------

    # UN_TRASH
    resp = await client.post(f"/v0/workspaces/{workspace.workspace_id}:untrash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # LIST NOT trashed (default)
    resp = await client.get("/v0/workspaces")
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].parse_obj(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].dict(exclude=_exclude_attrs) == workspace.dict(
        exclude=_exclude_attrs
    )

    assert page.data[0].trashed_at is None
    assert page.data[0].trashed_by is None

    # LIST trashed
    resp = await client.get("/v0/workspaces", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[WorkspaceGet].parse_obj(await resp.json())
    assert page.meta.total == 0
