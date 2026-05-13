# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_postgres_database.models.nodes_pending_deletion import (
    nodes_pending_deletion,
)
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.projects import (
    _node_pending_deletion_repository,
    _node_pending_deletion_service,
)


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
def user_id(logged_user: UserInfoDict) -> UserID:
    return logged_user["id"]


@pytest.fixture
def mock_storage_delete_data_folders_of_project_node(mocker: MockerFixture):
    """Mocks `delete_project_via_celery` AS imported by the node service-under-test.

    Name preserved for backward compat with existing tests; this is now the
    storage celery-job entry point that replaces the legacy HTTP cleanup.
    Also mocks `ProjectDBAPI.get_project_product` since the test project_id is
    a faker uuid not present in DB.
    """
    mocker.patch(
        "simcore_service_webserver.projects._node_pending_deletion_service.ProjectDBAPI.get_project_product",
        autospec=True,
        return_value="osparc",
    )
    return mocker.patch(
        "simcore_service_webserver.projects._node_pending_deletion_service.delete_project_via_celery",
        autospec=True,
        return_value=None,
    )


async def _outbox_row_for(
    app: web.Application, project_uuid: ProjectID, node_id: NodeID
) -> _node_pending_deletion_repository.NodePendingDeletionRow | None:
    rows = await _node_pending_deletion_repository.list_pending_deletions(app)
    matching = [r for r in rows if r["project_uuid"] == f"{project_uuid}" and r["node_id"] == f"{node_id}"]
    return matching[0] if matching else None


async def test_retry_pending_deletions_no_rows_is_noop(
    app: web.Application,
    mock_storage_delete_data_folders_of_project_node,
    clean_nodes_pending_deletion_table: None,
):
    await _node_pending_deletion_service.retry_pending_deletions(app)
    mock_storage_delete_data_folders_of_project_node.assert_not_called()


async def test_retry_pending_deletions_happy_path_clears_outbox(
    app: web.Application,
    project_id: ProjectID,
    node_id: NodeID,
    user_id: UserID,
    mock_storage_delete_data_folders_of_project_node,
    clean_nodes_pending_deletion_table: None,
):
    # arrange: outbox row simulating a node whose previous deletion attempt
    # crashed somewhere between the request and the storage cleanup.
    await _node_pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, node_id=node_id, requested_by=user_id
    )

    # act
    await _node_pending_deletion_service.retry_pending_deletions(app)

    # assert: storage cleanup was driven, outbox row gone
    mock_storage_delete_data_folders_of_project_node.assert_called_once()
    assert await _outbox_row_for(app, project_id, node_id) is None


async def test_retry_pending_deletions_storage_failure_keeps_row_and_records_error(
    app: web.Application,
    project_id: ProjectID,
    node_id: NodeID,
    user_id: UserID,
    mock_storage_delete_data_folders_of_project_node,
    clean_nodes_pending_deletion_table: None,
):
    mock_storage_delete_data_folders_of_project_node.side_effect = RuntimeError("S3 boom")

    await _node_pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, node_id=node_id, requested_by=user_id
    )

    await _node_pending_deletion_service.retry_pending_deletions(app)

    row = await _outbox_row_for(app, project_id, node_id)
    assert row is not None, "row must stay so the next pass can retry"
    assert row["attempts"] == 1
    assert row["last_error"] is not None
    assert "S3 boom" in row["last_error"]
    assert row["last_attempt_at"] is not None


async def test_retry_pending_deletions_skips_rows_with_null_requested_by(
    app: web.Application,
    project_id: ProjectID,
    node_id: NodeID,
    user_id: UserID,
    mock_storage_delete_data_folders_of_project_node,
    clean_nodes_pending_deletion_table: None,
):
    # insert via repo, then NULL-out requested_by (simulates user deletion
    # cascading SET NULL).
    await _node_pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, node_id=node_id, requested_by=user_id
    )
    engine = get_asyncpg_engine(app)
    async with engine.begin() as conn:
        await conn.execute(
            nodes_pending_deletion.update()
            .where(
                (nodes_pending_deletion.c.project_uuid == f"{project_id}")
                & (nodes_pending_deletion.c.node_id == f"{node_id}")
            )
            .values(requested_by=None)
        )

    await _node_pending_deletion_service.retry_pending_deletions(app)

    mock_storage_delete_data_folders_of_project_node.assert_not_called()
    row = await _outbox_row_for(app, project_id, node_id)
    assert row is not None, "row must remain for ops to inspect"
    assert row["attempts"] == 0


async def test_retry_pending_deletions_dead_letters_after_max_attempts(
    app: web.Application,
    project_id: ProjectID,
    node_id: NodeID,
    user_id: UserID,
    mock_storage_delete_data_folders_of_project_node,
    clean_nodes_pending_deletion_table: None,
):
    await _node_pending_deletion_repository.upsert_pending_deletion(
        app, project_uuid=project_id, node_id=node_id, requested_by=user_id
    )
    # bump attempts past the threshold
    engine = get_asyncpg_engine(app)
    async with engine.begin() as conn:
        await conn.execute(
            nodes_pending_deletion.update()
            .where(
                (nodes_pending_deletion.c.project_uuid == f"{project_id}")
                & (nodes_pending_deletion.c.node_id == f"{node_id}")
            )
            .values(attempts=10, last_error="prior failure")
        )

    await _node_pending_deletion_service.retry_pending_deletions(app, max_attempts=10)

    mock_storage_delete_data_folders_of_project_node.assert_not_called()
    row = await _outbox_row_for(app, project_id, node_id)
    assert row is not None, "dead-lettered row must remain for ops"
    assert row["attempts"] == 10
