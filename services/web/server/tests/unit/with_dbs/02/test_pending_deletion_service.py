# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_postgres_database.models.projects_pending_deletion import (
    projects_pending_deletion,
)
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.projects import (
    _pending_deletion_repository,
    _pending_deletion_service,
)
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
def app(client: TestClient) -> web.Application:
    assert client.app
    return client.app


@pytest.fixture
def project_id(user_project: ProjectDict) -> ProjectID:
    return ProjectID(user_project["uuid"])


@pytest.fixture
def user_id(logged_user: UserInfoDict) -> UserID:
    return logged_user["id"]


@pytest.fixture
def mock_storage_delete_data_folders_of_project(mocker: MockerFixture):
    """Mocks `delete_project_via_celery` AS imported by the service-under-test.

    Name preserved for backward compat with existing tests; this is now the
    storage celery-job entry point that replaces the legacy HTTP cleanup.
    """
    return mocker.patch(
        "simcore_service_webserver.projects._pending_deletion_service.delete_project_via_celery",
        autospec=True,
        return_value=None,
    )


async def _outbox_row_for(
    app: web.Application, project_uuid: ProjectID
) -> _pending_deletion_repository.PendingDeletionRow | None:
    rows = await _pending_deletion_repository.list_pending_deletions(app)
    matching = [r for r in rows if r["project_uuid"] == f"{project_uuid}"]
    return matching[0] if matching else None


async def test_retry_pending_deletions_no_rows_is_noop(
    app: web.Application,
    mock_storage_delete_data_folders_of_project,
    clean_projects_pending_deletion_table: None,
):
    await _pending_deletion_service.retry_pending_deletions(app)
    mock_storage_delete_data_folders_of_project.assert_not_called()


async def test_retry_pending_deletions_happy_path_clears_outbox_and_deletes_project(
    app: web.Application,
    project_id: ProjectID,
    user_id: UserID,
    mock_storage_delete_data_folders_of_project,
    clean_projects_pending_deletion_table: None,
):
    # arrange: outbox row simulating a project whose previous deletion attempt
    # crashed somewhere between storage cleanup and `db.delete_project`.
    await _pending_deletion_repository.upsert_pending_deletion(app, project_uuid=project_id, requested_by=user_id)

    # act
    await _pending_deletion_service.retry_pending_deletions(app)

    # assert: storage cleanup was driven, outbox row gone
    mock_storage_delete_data_folders_of_project.assert_called_once()
    assert await _outbox_row_for(app, project_id) is None


async def test_retry_pending_deletions_storage_failure_keeps_row_and_records_error(
    app: web.Application,
    project_id: ProjectID,
    user_id: UserID,
    mock_storage_delete_data_folders_of_project,
    clean_projects_pending_deletion_table: None,
):
    mock_storage_delete_data_folders_of_project.side_effect = RuntimeError("S3 boom")

    await _pending_deletion_repository.upsert_pending_deletion(app, project_uuid=project_id, requested_by=user_id)

    await _pending_deletion_service.retry_pending_deletions(app)

    row = await _outbox_row_for(app, project_id)
    assert row is not None, "row must stay so the next pass can retry"
    assert row["attempts"] == 1
    assert row["last_error"] is not None
    assert "S3 boom" in row["last_error"]
    assert row["last_attempt_at"] is not None


async def test_retry_pending_deletions_db_failure_keeps_row_and_records_error(
    app: web.Application,
    project_id: ProjectID,
    user_id: UserID,
    mock_storage_delete_data_folders_of_project,
    clean_projects_pending_deletion_table: None,
    mocker: MockerFixture,
):
    # storage step succeeds; db.delete_project blows up
    mocker.patch(
        "simcore_service_webserver.projects._pending_deletion_service.ProjectDBAPI.delete_project",
        autospec=True,
        side_effect=RuntimeError("db boom"),
    )

    await _pending_deletion_repository.upsert_pending_deletion(app, project_uuid=project_id, requested_by=user_id)

    await _pending_deletion_service.retry_pending_deletions(app)

    mock_storage_delete_data_folders_of_project.assert_called_once()
    row = await _outbox_row_for(app, project_id)
    assert row is not None
    assert row["attempts"] == 1
    assert row["last_error"] is not None
    assert "db boom" in row["last_error"]


async def test_retry_pending_deletions_skips_rows_with_null_requested_by(
    app: web.Application,
    project_id: ProjectID,
    user_id: UserID,
    mock_storage_delete_data_folders_of_project,
    clean_projects_pending_deletion_table: None,
):
    # insert via repo, then NULL-out requested_by (simulates user deletion
    # cascading SET NULL).
    await _pending_deletion_repository.upsert_pending_deletion(app, project_uuid=project_id, requested_by=user_id)
    engine = get_asyncpg_engine(app)
    async with engine.begin() as conn:
        await conn.execute(
            projects_pending_deletion.update()
            .where(projects_pending_deletion.c.project_uuid == f"{project_id}")
            .values(requested_by=None)
        )

    await _pending_deletion_service.retry_pending_deletions(app)

    mock_storage_delete_data_folders_of_project.assert_not_called()
    row = await _outbox_row_for(app, project_id)
    assert row is not None, "row must remain for ops to inspect"
    assert row["attempts"] == 0


async def test_retry_pending_deletions_dead_letters_after_max_attempts(
    app: web.Application,
    project_id: ProjectID,
    user_id: UserID,
    mock_storage_delete_data_folders_of_project,
    clean_projects_pending_deletion_table: None,
):
    await _pending_deletion_repository.upsert_pending_deletion(app, project_uuid=project_id, requested_by=user_id)
    # bump attempts past the threshold
    engine = get_asyncpg_engine(app)
    async with engine.begin() as conn:
        await conn.execute(
            projects_pending_deletion.update()
            .where(projects_pending_deletion.c.project_uuid == f"{project_id}")
            .values(attempts=10, last_error="prior failure")
        )

    await _pending_deletion_service.retry_pending_deletions(app, max_attempts=10)

    mock_storage_delete_data_folders_of_project.assert_not_called()
    row = await _outbox_row_for(app, project_id)
    assert row is not None, "dead-lettered row must remain for ops"
    assert row["attempts"] == 10
