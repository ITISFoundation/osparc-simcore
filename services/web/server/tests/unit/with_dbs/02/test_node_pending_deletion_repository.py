# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from datetime import UTC, datetime

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.projects import _node_pending_deletion_repository


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
def node_id(faker: Faker) -> NodeID:
    return NodeID(faker.uuid4())


@pytest.fixture
def other_node_id(faker: Faker) -> NodeID:
    return NodeID(faker.uuid4())


@pytest.fixture
def user_id(logged_user: UserInfoDict) -> UserID:
    return logged_user["id"]


async def test_upsert_then_list_returns_inserted_row(
    app: web.Application,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    clean_nodes_pending_deletion_table: None,
):
    await _node_pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, node_id=node_id, requested_by=user_id
    )

    rows = await _node_pending_deletion_repository.list_pending_deletions(app)
    matching = [r for r in rows if r["project_uuid"] == f"{project_id}" and r["node_id"] == f"{node_id}"]
    assert len(matching) == 1
    row = matching[0]
    assert row["requested_by"] == user_id
    assert row["attempts"] == 0
    assert row["last_attempt_at"] is None
    assert row["last_error"] is None
    assert row["storage_task_uuid"] is None


async def test_upsert_is_idempotent_and_preserves_original_requester(
    app: web.Application,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    clean_nodes_pending_deletion_table: None,
):
    other_user_id = user_id + 12345

    await _node_pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, node_id=node_id, requested_by=user_id
    )
    await _node_pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, node_id=node_id, requested_by=other_user_id
    )

    rows = await _node_pending_deletion_repository.list_pending_deletions(app)
    matching = [r for r in rows if r["project_uuid"] == f"{project_id}" and r["node_id"] == f"{node_id}"]
    assert len(matching) == 1, "second upsert must not create a duplicate row"
    assert matching[0]["requested_by"] == user_id


async def test_record_failed_attempt_increments_and_stores_error(
    app: web.Application,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    clean_nodes_pending_deletion_table: None,
):
    await _node_pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, node_id=node_id, requested_by=user_id
    )
    await _node_pending_deletion_repository.record_failed_attempt(
        app, project_uuid=project_id, node_id=node_id, error_message="boom-1"
    )
    await _node_pending_deletion_repository.record_failed_attempt(
        app, project_uuid=project_id, node_id=node_id, error_message="boom-2"
    )

    rows = await _node_pending_deletion_repository.list_pending_deletions(app)
    row = next(r for r in rows if r["project_uuid"] == f"{project_id}" and r["node_id"] == f"{node_id}")
    assert row["attempts"] == 2
    assert row["last_error"] == "boom-2"
    assert row["last_attempt_at"] is not None
    assert isinstance(row["last_attempt_at"], datetime)
    delta = datetime.now(tz=UTC) - row["last_attempt_at"]
    assert delta.total_seconds() < 60


async def test_delete_pending_deletion_removes_row(
    app: web.Application,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    clean_nodes_pending_deletion_table: None,
):
    await _node_pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, node_id=node_id, requested_by=user_id
    )
    await _node_pending_deletion_repository.delete_pending_deletion(app, project_uuid=project_id, node_id=node_id)

    rows = await _node_pending_deletion_repository.list_pending_deletions(app)
    assert all(not (r["project_uuid"] == f"{project_id}" and r["node_id"] == f"{node_id}") for r in rows)


async def test_delete_pending_deletion_is_noop_when_absent(
    app: web.Application,
    project_id: ProjectID,
    node_id: NodeID,
    clean_nodes_pending_deletion_table: None,
):
    # must not raise
    await _node_pending_deletion_repository.delete_pending_deletion(app, project_uuid=project_id, node_id=node_id)


async def test_two_nodes_in_same_project_coexist(
    app: web.Application,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    other_node_id: NodeID,
    clean_nodes_pending_deletion_table: None,
):
    # Composite PK on (project_uuid, node_id) must allow two distinct nodes
    # of the same project to be queued at the same time.
    await _node_pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, node_id=node_id, requested_by=user_id
    )
    await _node_pending_deletion_repository.upsert_pending_deletion(
        app,
        project_uuid=project_id,
        node_id=other_node_id,
        requested_by=user_id,
    )

    rows = await _node_pending_deletion_repository.list_pending_deletions(app)
    ours = [r for r in rows if r["project_uuid"] == f"{project_id}"]
    assert {r["node_id"] for r in ours} == {f"{node_id}", f"{other_node_id}"}
