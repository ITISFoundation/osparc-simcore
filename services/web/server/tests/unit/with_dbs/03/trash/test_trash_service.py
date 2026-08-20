# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from copy import deepcopy
from unittest.mock import MagicMock

import arrow
import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.rest_pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import (
    UserInfoDict,
    switch_client_session_to,
)
from pytest_simcore.helpers.webserver_projects import create_project
from servicelib.aiohttp import status
from simcore_postgres_database.models.folders_v2 import folders_v2
from simcore_postgres_database.models.workspaces import workspaces as workspaces_table
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.models import projects as projects_table
from simcore_service_webserver.folders import _folders_service
from simcore_service_webserver.projects import _projects_service_delete, _trash_service
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.trash import trash_service
from simcore_service_webserver.workspaces import _workspaces_service
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity import stop_after_attempt, wait_none


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    with_disabled_background_task_to_prune_trash: None,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "TRASH_RETENTION_DAYS": "0",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
        },
    )


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


async def test_trash_service__delete_expired_trash(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    other_user: UserInfoDict,
    other_user_project: ProjectDict,
    mocked_catalog: None,
    mocked_director_v2: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    mocked_storage: None,
):
    assert client.app
    assert logged_user["id"] != other_user["id"]

    # TRASH projects
    # logged_user trashes his project
    user_project_id = user_project["uuid"]
    await _trash_service.trash_project(
        client.app,
        product_name="osparc",
        user_id=logged_user["id"],
        project_id=user_project_id,
        force_stop_first=True,
        explicit=True,
    )

    # other_user trashes his project
    other_user_project_id = other_user_project["uuid"]
    await _trash_service.trash_project(
        client.app,
        product_name="osparc",
        user_id=other_user["id"],
        project_id=other_user_project_id,
        force_stop_first=True,
        explicit=True,
    )

    resp = await client.get(f"/v0/projects/{user_project_id}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert ProjectGet.model_validate(data).trashed_by == logged_user["primary_gid"]

    # UNDER TEST: Run delete_expired_trash
    await trash_service.safe_delete_expired_trash_as_admin(client.app)
    # ASSERT: logged_user tries to get the project and expects 404
    resp = await client.get(f"/v0/projects/{user_project_id}")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)

    # ASSERT: other_user tries to get the project and expects 404
    async with switch_client_session_to(client, other_user):
        resp = await client.get(f"/v0/projects/{other_user_project_id}")
        await assert_status(resp, status.HTTP_404_NOT_FOUND)


async def test_trash_service__delete_expired_trash_for_more_than_one_page_of_projects(
    client: TestClient,
    logged_user: UserInfoDict,
    fake_project: ProjectDict,
    mocked_catalog: None,
    mocked_director_v2: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    mocked_storage: None,
    asyncpg_engine: AsyncEngine,
):
    """Regression test for https://github.com/ITISFoundation/osparc-simcore/pull/9510:
    `batch_delete_trashed_projects_as_admin` used to raise a RuntimeError (aborting the whole
    GC run) as soon as more than one page (`MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE`) of trashed
    projects had to be deleted, because deleting a page's projects changes the count of the
    very collection `iter_pagination_params` was iterating over.
    """
    assert client.app

    num_projects = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE + 10  # forces more than one page

    created_project_ids: list[str] = []
    for _ in range(num_projects):
        project = await create_project(
            client.app, deepcopy(fake_project), user_id=logged_user["id"], product_name="osparc"
        )
        created_project_ids.append(project["uuid"])

    # TRASH all projects directly in the DB (bulk), already expired to bypass TRASH_RETENTION_DAYS timing
    already_expired = arrow.utcnow().shift(days=-1).datetime
    async with asyncpg_engine.begin() as conn:
        await conn.execute(
            projects_table.update()
            .where(projects_table.c.uuid.in_(created_project_ids))
            .values(trashed=already_expired, trashed_explicitly=True, trashed_by=logged_user["id"])
        )

    # UNDER TEST: a single GC cycle must delete ALL of them, without raising
    await trash_service.safe_delete_expired_trash_as_admin(client.app)

    # ASSERT: none of the projects remain in the DB
    async with asyncpg_engine.connect() as conn:
        result = await conn.execute(
            sa.select(projects_table.c.uuid).where(projects_table.c.uuid.in_(created_project_ids))
        )
        remaining_uuids = {row.uuid for row in result}
    assert not remaining_uuids


async def test_trash_service__delete_expired_trash_for_more_than_one_page_of_folders(
    client: TestClient,
    logged_user: UserInfoDict,
    asyncpg_engine: AsyncEngine,
):
    """Regression test for https://github.com/ITISFoundation/osparc-simcore/pull/9510:
    `batch_delete_trashed_folders_as_admin` had the same multi-page pagination bug as
    `batch_delete_trashed_projects_as_admin` (see the sibling projects test above).
    """
    assert client.app

    num_folders = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE + 10  # forces more than one page

    created_folder_ids: list[int] = []
    for i in range(num_folders):
        folder = await _folders_service.create_folder(
            client.app,
            user_id=logged_user["id"],
            name=f"folder-{i}",
            parent_folder_id=None,
            product_name="osparc",
            workspace_id=None,
        )
        created_folder_ids.append(folder.folder_db.folder_id)

    # TRASH all folders directly in the DB (bulk), already expired to bypass TRASH_RETENTION_DAYS timing
    already_expired = arrow.utcnow().shift(days=-1).datetime
    async with asyncpg_engine.begin() as conn:
        await conn.execute(
            folders_v2.update()
            .where(folders_v2.c.folder_id.in_(created_folder_ids))
            .values(trashed=already_expired, trashed_explicitly=True, trashed_by=logged_user["id"])
        )

    # UNDER TEST: a single GC cycle must delete ALL of them, without raising
    await trash_service.safe_delete_expired_trash_as_admin(client.app)

    # ASSERT: none of the folders remain in the DB
    async with asyncpg_engine.connect() as conn:
        result = await conn.execute(
            sa.select(folders_v2.c.folder_id).where(folders_v2.c.folder_id.in_(created_folder_ids))
        )
        remaining_ids = {row.folder_id for row in result}
    assert not remaining_ids


async def test_trash_service__delete_expired_trash_for_more_than_one_page_of_workspaces(
    client: TestClient,
    logged_user: UserInfoDict,
    asyncpg_engine: AsyncEngine,
):
    """Regression test for https://github.com/ITISFoundation/osparc-simcore/pull/9510:
    `batch_delete_trashed_workspaces_as_admin` had the same multi-page pagination bug as
    `batch_delete_trashed_projects_as_admin` (see the sibling projects test above).
    """
    assert client.app

    num_workspaces = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE + 10  # forces more than one page

    created_workspace_ids: list[int] = []
    for i in range(num_workspaces):
        workspace = await _workspaces_service.create_workspace(
            client.app,
            user_id=logged_user["id"],
            name=f"workspace-{i}",
            description=None,
            thumbnail=None,
            product_name="osparc",
        )
        created_workspace_ids.append(workspace.workspace_id)

    # TRASH all workspaces directly in the DB (bulk), already expired to bypass TRASH_RETENTION_DAYS timing
    already_expired = arrow.utcnow().shift(days=-1).datetime
    async with asyncpg_engine.begin() as conn:
        await conn.execute(
            workspaces_table.update()
            .where(workspaces_table.c.workspace_id.in_(created_workspace_ids))
            .values(trashed=already_expired, trashed_by=logged_user["id"])
        )

    # UNDER TEST: a single GC cycle must delete ALL of them, without raising
    await trash_service.safe_delete_expired_trash_as_admin(client.app)

    # ASSERT: none of the workspaces remain in the DB
    async with asyncpg_engine.connect() as conn:
        result = await conn.execute(
            sa.select(workspaces_table.c.workspace_id).where(workspaces_table.c.workspace_id.in_(created_workspace_ids))
        )
        remaining_ids = {row.workspace_id for row in result}
    assert not remaining_ids


async def test_trash_service__delete_expired_trash_retries_pipeline_stop_and_succeeds(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mocked_catalog: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    mocked_storage: None,
    mocker: MockerFixture,
):
    """Regression test: the computational pipeline takes a little while to stop (director-v2
    reports it as still running for a couple of checks). A single GC cycle must retry
    `_wait_for_pipeline_to_stop` internally until it succeeds, instead of deleting the project
    prematurely (see https://github.com/ITISFoundation/osparc-simcore/pull/9433).
    """
    assert client.app

    # speed up the tenacity retry so the test does not wait up to 60s.
    # NOTE: use an attempt-count bound (not `stop_after_delay`) so the retry isn't at the
    # mercy of wall-clock timing on a busy/slow CI runner (a wall-clock bound previously
    # caused flakiness: only 1 of the 3 expected calls happened before the bound elapsed).
    # 3 attempts exactly matches the `side_effect` list below.
    mocker.patch.object(_projects_service_delete._wait_for_pipeline_to_stop.retry, "wait", wait_none())  # noqa: SLF001
    mocker.patch.object(_projects_service_delete._wait_for_pipeline_to_stop.retry, "stop", stop_after_attempt(3))  # noqa: SLF001

    # simulate: pipeline is still running for the first 2 checks, then reports as stopped
    mock_is_pipeline_running = mocked_dynamic_services_interface["director_v2.api.is_pipeline_running"]
    mock_is_pipeline_running.side_effect = [True, True, False]

    user_project_id = user_project["uuid"]
    await _trash_service.trash_project(
        client.app,
        product_name="osparc",
        user_id=logged_user["id"],
        project_id=user_project_id,
        force_stop_first=True,
        explicit=True,
    )

    # UNDER TEST: a single GC cycle must retry internally until the pipeline is confirmed stopped
    await trash_service.safe_delete_expired_trash_as_admin(client.app)

    # exactly 3: matches the `side_effect` list above (2 "still running" + 1 "stopped")
    assert mock_is_pipeline_running.call_count == 3

    resp = await client.get(f"/v0/projects/{user_project_id}")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)


async def test_trash_service__delete_expired_trash_retries_across_gc_cycles_when_pipeline_stuck(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mocked_catalog: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    mocked_storage: None,
    mocker: MockerFixture,
    asyncpg_engine: AsyncEngine,
):
    """Regression test for the "eventually works" GC guarantee documented in
    `projects._trash_service` (NOTE above `trash_project_for_immediate_deletion`): if the pipeline
    never stops in time on one GC cycle, the project must survive (not be half-deleted), and a
    later GC cycle -once the pipeline finally stops- must complete the deletion.
    """
    assert client.app

    # pipeline is stuck/never reports as stopped
    mock_is_pipeline_running = mocked_dynamic_services_interface["director_v2.api.is_pipeline_running"]
    mock_is_pipeline_running.return_value = True

    # speed up the retry so a stuck GC cycle gives up quickly instead of waiting up to 60s.
    # NOTE: use an attempt-count bound (not `stop_after_delay`) to avoid wall-clock timing
    # flakiness on a busy/slow CI runner: the pipeline is stuck (always "running"), so the
    # exact attempt count just needs to be small, not timing-dependent.
    mocker.patch.object(_projects_service_delete._wait_for_pipeline_to_stop.retry, "wait", wait_none())  # noqa: SLF001
    mocker.patch.object(_projects_service_delete._wait_for_pipeline_to_stop.retry, "stop", stop_after_attempt(3))  # noqa: SLF001

    user_project_id = user_project["uuid"]
    await _trash_service.trash_project(
        client.app,
        product_name="osparc",
        user_id=logged_user["id"],
        project_id=user_project_id,
        force_stop_first=True,
        explicit=True,
    )

    async def _project_exists_in_db() -> bool:
        async with asyncpg_engine.connect() as conn:
            result = await conn.execute(
                sa.select(projects_table.c.uuid).where(projects_table.c.uuid == user_project_id)
            )
            return result.one_or_none() is not None

    assert await _project_exists_in_db()

    # CYCLE 1: pipeline never stops in time -> delete_project_as_admin raises ProjectDeleteError,
    # which the batch catches (fail_fast=False); the project must survive for the next cycle
    await trash_service.safe_delete_expired_trash_as_admin(client.app)
    assert await _project_exists_in_db()

    # the pipeline finally stops
    mock_is_pipeline_running.return_value = False

    # CYCLE 2: this time the GC succeeds
    await trash_service.safe_delete_expired_trash_as_admin(client.app)
    assert not await _project_exists_in_db()


async def test_trash_service__delete_expired_trash_for_nested_folders_and_projects(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    other_user: UserInfoDict,
    other_user_project: ProjectDict,
    mocked_catalog: None,
    mocked_director_v2: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    mocked_storage: None,
):
    assert client.app
    assert logged_user["id"] != other_user["id"]

    async with switch_client_session_to(client, logged_user):
        # CREATE folders hierarchy for logged_user
        resp = await client.post("/v0/folders", json={"name": "Root Folder"})
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        logged_user_root_folder = data

        resp = await client.post(
            "/v0/folders",
            json={
                "name": "Sub Folder",
                "parentFolderId": logged_user_root_folder["folderId"],
            },
        )
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        logged_user_sub_folder = data

        # MOVE project to subfolder
        resp = await client.put(f"/v0/projects/{user_project['uuid']}/folders/{logged_user_sub_folder['folderId']}")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        # TRASH root folders
        resp = await client.post(f"/v0/folders/{logged_user_root_folder['folderId']}:trash")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

    async with switch_client_session_to(client, other_user):
        # CREATE folders hierarchy for other_user
        resp = await client.post("/v0/folders", json={"name": "Root Folder"})
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        other_user_root_folder = data

        resp = await client.post(
            "/v0/folders",
            json={
                "name": "Sub Folder (other)",
                "parentFolderId": other_user_root_folder["folderId"],
            },
        )
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        other_user_sub_folder = data

        # MOVE project to subfolder
        resp = await client.put(
            f"/v0/projects/{other_user_project['uuid']}/folders/{other_user_sub_folder['folderId']}"
        )
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        # TRASH root folders
        resp = await client.post(f"/v0/folders/{other_user_root_folder['folderId']}:trash")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # UNDER TEST
    await trash_service.safe_delete_expired_trash_as_admin(client.app)

    async with switch_client_session_to(client, logged_user):
        # Verify logged_user's resources are gone
        resp = await client.get(f"/v0/folders/{logged_user_root_folder['folderId']}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        resp = await client.get(f"/v0/folders/{logged_user_sub_folder['folderId']}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        resp = await client.get(f"/v0/projects/{user_project['uuid']}")
        await assert_status(resp, status.HTTP_404_NOT_FOUND)

    # Verify other_user's resources are gone
    async with switch_client_session_to(client, other_user):
        resp = await client.get(f"/v0/folders/{other_user_root_folder['folderId']}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        resp = await client.get(f"/v0/folders/{other_user_sub_folder['folderId']}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        resp = await client.get(f"/v0/projects/{other_user_project['uuid']}")
        await assert_status(resp, status.HTTP_404_NOT_FOUND)


async def test_trash_service__delete_expired_trash_for_workspace(  # noqa: PLR0915
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    other_user: UserInfoDict,
    other_user_project: ProjectDict,
    mocked_catalog: None,
    mocked_director_v2: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    mocked_storage: None,
):
    assert client.app
    assert logged_user["id"] != other_user["id"]

    async with switch_client_session_to(client, logged_user):
        # CREATE folders hierarchy for logged_user
        resp = await client.post("/v0/folders", json={"name": "Root Folder"})
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        logged_user_root_folder = data

        resp = await client.post(
            "/v0/folders",
            json={
                "name": "Sub Folder",
                "parentFolderId": logged_user_root_folder["folderId"],
            },
        )
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        logged_user_sub_folder = data

        # MOVE project to subfolder
        resp = await client.put(f"/v0/projects/{user_project['uuid']}/folders/{logged_user_sub_folder['folderId']}")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        # CREATE workspace
        resp = await client.post("/v0/workspaces", json={"name": "My Workspace"})
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        logged_user_workspace = data

        # MOVE root folder with content to workspace
        url = client.app.router["move_folder_to_workspace"].url_for(
            folder_id=f"{logged_user_root_folder['folderId']}",
            workspace_id=f"{logged_user_workspace['workspaceId']}",
        )
        resp = await client.post(f"{url}")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        # TRASH workspace
        resp = await client.post(f"/v0/workspaces/{logged_user_workspace['workspaceId']}:trash")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

    async with switch_client_session_to(client, other_user):
        # CREATE folders hierarchy for other_user
        resp = await client.post("/v0/folders", json={"name": "Root Folder"})
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        other_user_root_folder = data

        resp = await client.post(
            "/v0/folders",
            json={
                "name": "Sub Folder (other)",
                "parentFolderId": other_user_root_folder["folderId"],
            },
        )
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        other_user_sub_folder = data

        # MOVE project to subfolder
        resp = await client.put(
            f"/v0/projects/{other_user_project['uuid']}/folders/{other_user_sub_folder['folderId']}"
        )
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        # CREATE workspace
        resp = await client.post("/v0/workspaces", json={"name": "Other User Workspace"})
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        other_user_workspace = data

        # MOVE Folder to workspace
        url = client.app.router["move_folder_to_workspace"].url_for(
            folder_id=f"{other_user_root_folder['folderId']}",
            workspace_id=f"{other_user_workspace['workspaceId']}",
        )
        resp = await client.post(f"{url}")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        # TRASH workspace
        resp = await client.post(f"/v0/workspaces/{other_user_workspace['workspaceId']}:trash")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # UNDER TEST
    await trash_service.safe_delete_expired_trash_as_admin(client.app)

    async with switch_client_session_to(client, logged_user):
        # Verify logged_user's resources are gone
        resp = await client.get(f"/v0/workspaces/{logged_user_workspace['workspaceId']}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        resp = await client.get(f"/v0/folders/{logged_user_root_folder['folderId']}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        resp = await client.get(f"/v0/folders/{logged_user_sub_folder['folderId']}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        resp = await client.get(f"/v0/projects/{user_project['uuid']}")
        await assert_status(resp, status.HTTP_404_NOT_FOUND)

    # Verify other_user's resources are gone
    async with switch_client_session_to(client, other_user):
        resp = await client.get(f"/v0/workspaces/{other_user_workspace['workspaceId']}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        resp = await client.get(f"/v0/folders/{other_user_root_folder['folderId']}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        resp = await client.get(f"/v0/folders/{other_user_sub_folder['folderId']}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        resp = await client.get(f"/v0/projects/{other_user_project['uuid']}")
        await assert_status(resp, status.HTTP_404_NOT_FOUND)


async def test_trash_service__delete_expired_trash_for_workspace_retries_across_gc_cycles_when_one_project_fails(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_catalog: None,
    mocked_dynamic_services_interface: dict[str, MagicMock],
    mocker: MockerFixture,
    asyncpg_engine: AsyncEngine,
    fake_project: ProjectDict,
):
    """Regression test for the per-workspace guard in
    `workspaces._trash_service.batch_delete_trashed_workspaces_as_admin`: if one trashed
    workspace's project deletion fails, that workspace (and its still-undeleted project) must
    survive - NOT be hard-deleted via `ON DELETE CASCADE` - while OTHER trashed workspaces in the
    same GC batch must still be deleted normally (best-effort, matches outer `fail_fast=False`).
    A later GC cycle -once the fault is fixed- must complete the deletion of the previously-stuck
    workspace.
    """
    assert client.app

    mocker.patch(
        "simcore_service_webserver.projects._projects_service.remove_project_dynamic_services",
        autospec=True,
    )

    # CREATE workspace A (its project will fail to delete) with one project
    resp = await client.post("/v0/workspaces", json={"name": "Workspace A (will fail)"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    workspace_a = data
    project_a_data = deepcopy(fake_project)
    project_a_data["workspace_id"] = f"{workspace_a['workspaceId']}"
    project_a = await create_project(client.app, project_a_data, user_id=logged_user["id"], product_name="osparc")

    # CREATE workspace B (will succeed normally) with one project
    resp = await client.post("/v0/workspaces", json={"name": "Workspace B (will succeed)"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    workspace_b = data
    project_b_data = deepcopy(fake_project)
    project_b_data["workspace_id"] = f"{workspace_b['workspaceId']}"
    project_b = await create_project(client.app, project_b_data, user_id=logged_user["id"], product_name="osparc")

    # storage deletion fails only for project A
    async def _delete_project_data_folders_side_effect(_app, *, project_id, **_kwargs):
        if f"{project_id}" == project_a["uuid"]:
            msg = "simulated storage failure for project A"
            raise RuntimeError(msg)

    mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.storage_service.delete_project_data_folders",
        side_effect=_delete_project_data_folders_side_effect,
    )

    # TRASH both workspaces
    resp = await client.post(f"/v0/workspaces/{workspace_a['workspaceId']}:trash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)
    resp = await client.post(f"/v0/workspaces/{workspace_b['workspaceId']}:trash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    async def _workspace_exists_in_db(workspace_id) -> bool:
        async with asyncpg_engine.connect() as conn:
            result = await conn.execute(
                sa.select(workspaces_table.c.workspace_id).where(workspaces_table.c.workspace_id == int(workspace_id))
            )
            return result.one_or_none() is not None

    async def _project_exists_in_db(project_uuid) -> bool:
        async with asyncpg_engine.connect() as conn:
            result = await conn.execute(sa.select(projects_table.c.uuid).where(projects_table.c.uuid == project_uuid))
            return result.one_or_none() is not None

    # CYCLE 1: workspace A's project fails to delete -> workspace A (and project A) must survive;
    # workspace B must still be fully deleted in the SAME cycle (best-effort across workspaces)
    await trash_service.safe_delete_expired_trash_as_admin(client.app)

    assert await _workspace_exists_in_db(workspace_a["workspaceId"])
    assert await _project_exists_in_db(project_a["uuid"])

    assert not await _workspace_exists_in_db(workspace_b["workspaceId"])
    assert not await _project_exists_in_db(project_b["uuid"])

    # fix the fault
    mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.storage_service.delete_project_data_folders",
        return_value=None,
    )

    # CYCLE 2: workspace A is retried and now succeeds
    await trash_service.safe_delete_expired_trash_as_admin(client.app)

    assert not await _workspace_exists_in_db(workspace_a["workspaceId"])
    assert not await _project_exists_in_db(project_a["uuid"])
