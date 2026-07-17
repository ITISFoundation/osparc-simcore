# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.projects import ProjectGet
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import (
    UserInfoDict,
    switch_client_session_to,
)
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.models import projects as projects_table
from simcore_service_webserver.projects import _projects_service_delete, _trash_service
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.trash import trash_service
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity import stop_after_delay, wait_fixed


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

    # speed up the tenacity retry so the test does not wait up to 60s
    mocker.patch.object(_projects_service_delete._wait_for_pipeline_to_stop.retry, "wait", wait_fixed(0.05))  # noqa: SLF001
    mocker.patch.object(_projects_service_delete._wait_for_pipeline_to_stop.retry, "stop", stop_after_delay(2))  # noqa: SLF001

    mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.director_v2_service.stop_pipeline",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.director_v2_service.delete_pipeline",
        autospec=True,
    )
    # simulate: pipeline is still running for the first 2 checks, then reports as stopped
    mock_is_pipeline_running = mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.director_v2_service.is_pipeline_running",
        autospec=True,
        side_effect=[True, True, False],
    )

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

    assert mock_is_pipeline_running.call_count >= 3

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

    mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.director_v2_service.stop_pipeline",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.director_v2_service.delete_pipeline",
        autospec=True,
    )
    # pipeline is stuck/never reports as stopped
    mock_is_pipeline_running = mocker.patch(
        "simcore_service_webserver.projects._projects_service_delete.director_v2_service.is_pipeline_running",
        autospec=True,
        return_value=True,
    )

    # speed up the retry so a stuck GC cycle gives up quickly instead of waiting up to 60s
    mocker.patch.object(_projects_service_delete._wait_for_pipeline_to_stop.retry, "wait", wait_fixed(0.05))  # noqa: SLF001
    mocker.patch.object(_projects_service_delete._wait_for_pipeline_to_stop.retry, "stop", stop_after_delay(0.3))  # noqa: SLF001

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
