# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from datetime import UTC, datetime

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from faker import Faker
from models_library.projects import ProjectID
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.projects import _pending_deletion_repository


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
def app(client: TestClient) -> web.Application:
    assert client.app
    return client.app


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


@pytest.fixture
def other_project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


async def test_upsert_then_list_returns_inserted_row(
    app: web.Application,
    logged_user: UserInfoDict,
    project_id: ProjectID,
    clean_projects_pending_deletion_table: None,
):
    await _pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, requested_by=logged_user["id"]
    )

    rows = await _pending_deletion_repository.list_pending_deletions(app)
    matching = [r for r in rows if r["project_uuid"] == f"{project_id}"]
    assert len(matching) == 1
    row = matching[0]
    assert row["requested_by"] == logged_user["id"]
    assert row["attempts"] == 0
    assert row["last_attempt_at"] is None
    assert row["last_error"] is None
    assert row["storage_task_uuid"] is None


async def test_upsert_is_idempotent_and_preserves_original_requester(
    app: web.Application,
    logged_user: UserInfoDict,
    project_id: ProjectID,
    clean_projects_pending_deletion_table: None,
):
    # NOTE: simulate a second deletion request landing while the first is
    # still in flight; ON CONFLICT DO NOTHING must keep the original
    # requested_by (and the running attempts/last_error) intact.
    other_user_id = logged_user["id"] + 12345

    await _pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, requested_by=logged_user["id"]
    )
    await _pending_deletion_repository.upsert_pending_deletion(app, project_uuid=project_id, requested_by=other_user_id)

    rows = await _pending_deletion_repository.list_pending_deletions(app)
    matching = [r for r in rows if r["project_uuid"] == f"{project_id}"]
    assert len(matching) == 1, "second upsert must not create a duplicate row"
    assert matching[0]["requested_by"] == logged_user["id"]


async def test_record_failed_attempt_increments_and_stores_error(
    app: web.Application,
    logged_user: UserInfoDict,
    project_id: ProjectID,
    clean_projects_pending_deletion_table: None,
):
    await _pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, requested_by=logged_user["id"]
    )
    await _pending_deletion_repository.record_failed_attempt(app, project_uuid=project_id, error_message="boom-1")
    await _pending_deletion_repository.record_failed_attempt(app, project_uuid=project_id, error_message="boom-2")

    rows = await _pending_deletion_repository.list_pending_deletions(app)
    row = next(r for r in rows if r["project_uuid"] == f"{project_id}")
    assert row["attempts"] == 2
    assert row["last_error"] == "boom-2"
    assert row["last_attempt_at"] is not None
    assert isinstance(row["last_attempt_at"], datetime)
    # tolerate clock skew; just ensure it is recent
    delta = datetime.now(tz=UTC) - row["last_attempt_at"]
    assert delta.total_seconds() < 60


async def test_delete_pending_deletion_removes_row(
    app: web.Application,
    logged_user: UserInfoDict,
    project_id: ProjectID,
    clean_projects_pending_deletion_table: None,
):
    await _pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, requested_by=logged_user["id"]
    )
    await _pending_deletion_repository.delete_pending_deletion(app, project_uuid=project_id)

    rows = await _pending_deletion_repository.list_pending_deletions(app)
    assert all(r["project_uuid"] != f"{project_id}" for r in rows)


async def test_delete_pending_deletion_is_noop_when_absent(
    app: web.Application,
    logged_user: UserInfoDict,
    project_id: ProjectID,
    clean_projects_pending_deletion_table: None,
):
    # must not raise
    await _pending_deletion_repository.delete_pending_deletion(app, project_uuid=project_id)


async def test_list_pending_deletions_orders_never_attempted_first(
    app: web.Application,
    logged_user: UserInfoDict,
    project_id: ProjectID,
    other_project_id: ProjectID,
    clean_projects_pending_deletion_table: None,
):
    # insert the one we will mark as attempted FIRST so we can be sure ordering
    # is by `last_attempt_at` (nulls first), not by insertion order
    await _pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, requested_by=logged_user["id"]
    )
    await _pending_deletion_repository.record_failed_attempt(app, project_uuid=project_id, error_message="boom")

    # now insert a never-attempted one; it must come first in the listing
    await _pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=other_project_id, requested_by=logged_user["id"]
    )

    rows = await _pending_deletion_repository.list_pending_deletions(app)
    ours = [r for r in rows if r["project_uuid"] in (f"{project_id}", f"{other_project_id}")]
    assert len(ours) == 2
    assert ours[0]["project_uuid"] == f"{other_project_id}"
    assert ours[0]["last_attempt_at"] is None
    assert ours[1]["project_uuid"] == f"{project_id}"
    assert ours[1]["last_attempt_at"] is not None
