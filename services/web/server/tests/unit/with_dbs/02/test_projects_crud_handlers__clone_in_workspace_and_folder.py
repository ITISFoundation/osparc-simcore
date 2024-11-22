# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from copy import deepcopy
from typing import Any, Iterator

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.folders import FolderID
from models_library.projects import ProjectID
from models_library.workspaces import WorkspaceID
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import MockedStorageSubsystem
from servicelib.aiohttp.long_running_tasks.client import long_running_task_request
from simcore_postgres_database.models.folders_v2 import folders_v2
from simcore_postgres_database.models.workspaces import workspaces
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.folders._folders_api import create_folder
from simcore_service_webserver.projects._folders_api import move_project_into_folder
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.workspaces._workspaces_api import create_workspace
from yarl import URL


@pytest.fixture
async def create_workspace_and_folder(
    client: TestClient, logged_user: UserInfoDict, postgres_db: sa.engine.Engine
) -> Iterator[tuple[WorkspaceID, FolderID]]:
    workspace = await create_workspace(
        client.app,
        user_id=logged_user["id"],
        name="a",
        description=None,
        thumbnail=None,
        product_name="osparc",
    )

    folder = await create_folder(
        client.app,
        user_id=logged_user["id"],
        name="a",
        parent_folder_id=None,
        product_name="osparc",
        workspace_id=workspace.workspace_id,
    )

    yield (workspace.workspace_id, folder.folder_id)

    with postgres_db.connect() as con:
        con.execute(folders_v2.delete())
        con.execute(workspaces.delete())


@pytest.fixture
def fake_project(
    fake_project: ProjectDict,
    workbench_db_column: dict[str, Any],
    create_workspace_and_folder: tuple[WorkspaceID, FolderID],
) -> ProjectDict:
    # OVERRIDES user_project
    project = deepcopy(fake_project)
    project["workbench"] = workbench_db_column
    project["workspaceId"] = create_workspace_and_folder[0]
    return project


async def _request_clone_project(client: TestClient, url: URL) -> ProjectGet:
    """Raise HTTPError subclasses if request fails"""
    # polls until long-running task is done
    data = None
    async for long_running_task in long_running_task_request(
        client.session, url=client.make_url(url.path), json=None, client_timeout=30
    ):
        print(f"{long_running_task.progress=}")
        if long_running_task.done():
            data = await long_running_task.result()

    assert data is not None
    return ProjectGet.model_validate(data)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_clone_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    # mocks backend
    storage_subsystem_mock: MockedStorageSubsystem,
    mock_catalog_service_api_responses: None,
    project_db_cleaner: None,
    create_workspace_and_folder: tuple[WorkspaceID, FolderID],
):
    assert client.app

    project = user_project
    await move_project_into_folder(
        client.app,
        user_id=logged_user["id"],
        project_id=project["uuid"],
        folder_id=create_workspace_and_folder[1],
        product_name="osparc",
    )

    base_url = client.app.router["list_projects"].url_for()
    query_parameters = {
        "workspace_id": f"{create_workspace_and_folder[0]}",
        "folder_id": f"{create_workspace_and_folder[1]}",
    }
    url = base_url.with_query(**query_parameters)
    resp = await client.get(f"{url}")
    data = await resp.json()
    assert resp.status == 200
    assert len(data["data"]) == 1

    url = client.app.router["clone_project"].url_for(project_id=project["uuid"])
    assert f"/v0/projects/{project['uuid']}:clone" == url.path

    cloned_project = await _request_clone_project(client, url)

    # check whether it's a clone
    assert ProjectID(project["uuid"]) != cloned_project.uuid
    assert cloned_project.workspace_id == create_workspace_and_folder[0]

    # check whether it's in right folder
    base_url = client.app.router["list_projects"].url_for()
    query_parameters = {
        "workspace_id": f"{create_workspace_and_folder[0]}",
        "folder_id": f"{create_workspace_and_folder[1]}",
    }
    url = base_url.with_query(**query_parameters)
    resp = await client.get(f"{url}")
    data = await resp.json()
    assert resp.status == 200
    assert len(data["data"]) == 2
