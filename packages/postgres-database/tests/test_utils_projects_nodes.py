# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import asyncio
import random
import uuid
from collections.abc import Awaitable, Callable
from random import randint
from typing import Any, Final

import pytest
import sqlalchemy
from faker import Faker
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_nodes import projects_nodes
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNodeCreate,
    ProjectNodesDuplicateNodeError,
    ProjectNodesNodeNotFoundError,
    ProjectNodesNonUniqueNodeFoundError,
    ProjectNodesProjectNotFoundError,
    ProjectNodesRepo,
    lock_project_for_write,
)
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


# NOTE: Temporary usage of asyncpg_connection until asyncpg is used
async def _delete_project(asyncpg_connection: AsyncConnection, project_uuid: uuid.UUID) -> None:
    result = await asyncpg_connection.execute(sqlalchemy.delete(projects).where(projects.c.uuid == f"{project_uuid}"))
    assert result.rowcount == 1


@pytest.fixture
async def registered_user(
    asyncpg_connection: AsyncConnection,
    create_fake_user: Callable[..., Awaitable[RowMapping]],
) -> RowMapping:
    user = await create_fake_user(asyncpg_connection)
    assert user
    return user


@pytest.fixture
async def registered_product(
    asyncpg_connection: AsyncConnection,
    create_fake_product: Callable[..., Awaitable[RowMapping]],
) -> RowMapping:
    product = await create_fake_product("test-product")
    assert product
    return product


@pytest.fixture
async def registered_project(
    asyncpg_connection: AsyncConnection,
    registered_user: RowMapping,
    registered_product: RowMapping,
    create_fake_project: Callable[..., Awaitable[RowMapping]],
) -> dict[str, Any]:
    project = await create_fake_project(asyncpg_connection, registered_user, registered_product)
    assert project
    return dict(project)


@pytest.fixture
def projects_nodes_repo_of_invalid_project(faker: Faker) -> ProjectNodesRepo:
    invalid_project_uuid = faker.uuid4(cast_to=None)
    assert isinstance(invalid_project_uuid, uuid.UUID)
    repo = ProjectNodesRepo(project_uuid=invalid_project_uuid)
    assert repo
    return repo


@pytest.fixture
def projects_nodes_repo(registered_project: dict[str, Any]) -> ProjectNodesRepo:
    repo = ProjectNodesRepo(project_uuid=registered_project["uuid"])
    assert repo
    return repo


@pytest.fixture
def create_fake_projects_node(
    faker: Faker,
) -> Callable[..., ProjectNodeCreate]:
    def _creator() -> ProjectNodeCreate:
        node = ProjectNodeCreate(
            node_id=uuid.uuid4(),
            required_resources=faker.pydict(allowed_types=(str,)),
            key=faker.pystr(),
            version=faker.pystr(),
            label=faker.pystr(),
        )
        assert node
        return node

    return _creator


async def test_create_projects_nodes_raises_if_project_not_found(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo_of_invalid_project: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
):
    with pytest.raises(ProjectNodesProjectNotFoundError):
        await projects_nodes_repo_of_invalid_project.add(
            asyncpg_connection,
            nodes=[create_fake_projects_node()],
        )


async def test_create_projects_nodes(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
):
    assert await projects_nodes_repo.add(asyncpg_connection, nodes=[]) == []

    new_nodes = await projects_nodes_repo.add(
        asyncpg_connection,
        nodes=[create_fake_projects_node()],
    )
    assert new_nodes
    assert len(new_nodes) == 1
    assert new_nodes[0]


async def test_create_twice_same_projects_nodes_raises(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
):
    node_create = create_fake_projects_node()
    new_nodes = await projects_nodes_repo.add(asyncpg_connection, nodes=[node_create])
    assert new_nodes
    assert len(new_nodes) == 1
    with pytest.raises(ProjectNodesDuplicateNodeError):
        await projects_nodes_repo.add(
            asyncpg_connection,
            nodes=[node_create],
        )


async def test_list_project_nodes_of_invalid_project_returns_nothing(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo_of_invalid_project: ProjectNodesRepo,
):
    nodes = await projects_nodes_repo_of_invalid_project.list(asyncpg_connection)
    assert nodes == []


async def test_list_project_nodes(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
):
    nodes = await projects_nodes_repo.list(asyncpg_connection)
    assert nodes == []

    created_nodes = await projects_nodes_repo.add(
        asyncpg_connection,
        nodes=[
            create_fake_projects_node()
            for _ in range(randint(3, 12))  # noqa: S311
        ],
    )

    nodes = await projects_nodes_repo.list(asyncpg_connection)
    assert nodes
    assert len(nodes) == len(created_nodes)


async def test_get_project_node_of_invalid_project_raises(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo_of_invalid_project: ProjectNodesRepo,
):
    with pytest.raises(ProjectNodesNodeNotFoundError):
        await projects_nodes_repo_of_invalid_project.get(asyncpg_connection, node_id=uuid.uuid4())


async def test_get_project_node_of_empty_project_raises(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo: ProjectNodesRepo,
):
    with pytest.raises(ProjectNodesNodeNotFoundError):
        await projects_nodes_repo.get(asyncpg_connection, node_id=uuid.uuid4())


async def test_get_project_node(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
):
    new_nodes = await projects_nodes_repo.add(asyncpg_connection, nodes=[create_fake_projects_node()])
    assert len(new_nodes) == 1
    assert new_nodes[0]

    received_node = await projects_nodes_repo.get(asyncpg_connection, node_id=new_nodes[0].node_id)

    assert received_node == new_nodes[0]


async def test_update_project_node_of_invalid_node_raises(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    faker: Faker,
):
    new_nodes = await projects_nodes_repo.add(
        asyncpg_connection,
        nodes=[create_fake_projects_node()],
    )
    assert len(new_nodes) == 1
    assert new_nodes[0]
    assert new_nodes[0].created == new_nodes[0].modified
    with pytest.raises(ProjectNodesNodeNotFoundError):
        await projects_nodes_repo.update(
            asyncpg_connection,
            node_id=uuid.uuid4(),
            required_resources={faker.pystr(): faker.pyint()},
        )


async def test_update_project_node(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    faker: Faker,
):
    new_nodes = await projects_nodes_repo.add(asyncpg_connection, nodes=[create_fake_projects_node()])
    assert len(new_nodes) == 1
    assert new_nodes[0]
    assert new_nodes[0].created == new_nodes[0].modified
    required_resources = {faker.pystr(): faker.pyint()}
    updated_node = await projects_nodes_repo.update(
        asyncpg_connection,
        node_id=new_nodes[0].node_id,
        required_resources=required_resources,
    )
    assert updated_node
    assert updated_node != new_nodes
    assert updated_node.modified > new_nodes[0].modified
    assert updated_node.created == new_nodes[0].created
    assert updated_node.required_resources == required_resources


async def test_delete_invalid_node_does_nothing(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo_of_invalid_project: ProjectNodesRepo,
):
    await projects_nodes_repo_of_invalid_project.delete(asyncpg_connection, node_id=uuid.uuid4())


async def test_delete_node(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
):
    new_nodes = await projects_nodes_repo.add(
        asyncpg_connection,
        nodes=[create_fake_projects_node()],
    )
    assert len(new_nodes) == 1
    assert new_nodes[0]

    received_node = await projects_nodes_repo.get(asyncpg_connection, node_id=new_nodes[0].node_id)
    assert received_node == new_nodes[0]
    await projects_nodes_repo.delete(asyncpg_connection, node_id=new_nodes[0].node_id)

    with pytest.raises(ProjectNodesNodeNotFoundError):
        await projects_nodes_repo.get(asyncpg_connection, node_id=new_nodes[0].node_id)


async def test_delete_project_delete_all_nodes(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
):
    # create a project node
    new_nodes = await projects_nodes_repo.add(
        asyncpg_connection,
        nodes=[create_fake_projects_node()],
    )
    assert len(new_nodes) == 1
    assert new_nodes[0]
    received_node = await projects_nodes_repo.get(asyncpg_connection, node_id=new_nodes[0].node_id)
    assert received_node == new_nodes[0]

    # now delete the project from the projects table
    await _delete_project(asyncpg_connection, projects_nodes_repo.project_uuid)

    # the project cannot be found anymore (the link in projects_to_projects_nodes is auto-removed)
    with pytest.raises(ProjectNodesNodeNotFoundError):
        await projects_nodes_repo.get(asyncpg_connection, node_id=new_nodes[0].node_id)

    # the underlying projects_nodes should also be gone, thanks to migration
    result = await asyncpg_connection.execute(
        sqlalchemy.select(projects_nodes).where(projects_nodes.c.node_id == f"{new_nodes[0].node_id}")
    )
    assert result
    row = result.mappings().first()
    assert row is None


@pytest.mark.parametrize("num_concurrent_workflows", [1, 250])
async def test_multiple_creation_deletion_of_nodes(
    asyncpg_engine: AsyncEngine,
    registered_user: RowMapping,
    registered_product: RowMapping,
    create_fake_project: Callable[..., Awaitable[RowMapping]],
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    num_concurrent_workflows: int,
):
    NUM_NODES = 11

    async def _workflow() -> None:
        async with asyncpg_engine.connect() as connection:
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            project = await create_fake_project(connection, registered_user, registered_product)
            projects_nodes_repo = ProjectNodesRepo(project_uuid=project["uuid"])

            await projects_nodes_repo.add(
                connection,
                nodes=[create_fake_projects_node() for _ in range(NUM_NODES)],
            )
            list_nodes = await projects_nodes_repo.list(connection)
            assert list_nodes
            assert len(list_nodes) == NUM_NODES
            await projects_nodes_repo.delete(
                connection,
                node_id=random.choice(list_nodes).node_id,  # noqa: S311
            )
            list_nodes = await projects_nodes_repo.list(connection)
            assert list_nodes
            assert len(list_nodes) == (NUM_NODES - 1)
            await _delete_project(connection, project_uuid=project["uuid"])

    await asyncio.gather(*(_workflow() for _ in range(num_concurrent_workflows)))


async def test_get_project_id_from_node_id(
    asyncpg_engine: AsyncEngine,
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo: ProjectNodesRepo,
    registered_user: RowMapping,
    registered_product: RowMapping,
    create_fake_project: Callable[..., Awaitable[RowMapping]],
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
):
    NUM_NODES = 11

    async def _workflow() -> dict[uuid.UUID, list[uuid.UUID]]:
        async with asyncpg_engine.connect() as connection:
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            project = await create_fake_project(connection, registered_user, registered_product)
            projects_nodes_repo = ProjectNodesRepo(project_uuid=project["uuid"])

            list_of_nodes = await projects_nodes_repo.add(
                connection,
                nodes=[create_fake_projects_node() for _ in range(NUM_NODES)],
            )

        return {uuid.UUID(project["uuid"]): [node.node_id for node in list_of_nodes]}

    # create some projects
    list_of_project_id_node_ids_map = await asyncio.gather(*(_workflow() for _ in range(10)))

    for project_id_to_node_ids_map in list_of_project_id_node_ids_map:
        project_id = next(iter(project_id_to_node_ids_map))
        random_node_id = random.choice(  # noqa: S311
            project_id_to_node_ids_map[project_id]
        )
        received_project_id = await ProjectNodesRepo.get_project_id_from_node_id(
            asyncpg_connection, node_id=random_node_id
        )
        assert received_project_id == next(iter(project_id_to_node_ids_map))


async def test_get_project_id_from_node_id_raises_for_invalid_node_id(
    asyncpg_connection: AsyncConnection,
    faker: Faker,
):
    random_uuid = faker.uuid4(cast_to=None)
    assert isinstance(random_uuid, uuid.UUID)
    with pytest.raises(ProjectNodesNodeNotFoundError):
        await ProjectNodesRepo.get_project_id_from_node_id(asyncpg_connection, node_id=random_uuid)


async def test_get_project_id_from_node_id_raises_if_multiple_projects_with_same_node_id_exist(
    asyncpg_connection: AsyncConnection,
    projects_nodes_repo: ProjectNodesRepo,
    registered_user: RowMapping,
    registered_product: RowMapping,
    create_fake_project: Callable[..., Awaitable[RowMapping]],
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
):
    project1 = await create_fake_project(asyncpg_connection, registered_user, registered_product)
    project1_repo = ProjectNodesRepo(project_uuid=project1["uuid"])

    project2 = await create_fake_project(asyncpg_connection, registered_user, registered_product)
    project2_repo = ProjectNodesRepo(project_uuid=project2["uuid"])

    shared_node = create_fake_projects_node()

    project1_nodes = await project1_repo.add(asyncpg_connection, nodes=[shared_node])
    assert len(project1_nodes) == 1
    project2_nodes = await project2_repo.add(asyncpg_connection, nodes=[shared_node])
    assert len(project2_nodes) == 1
    assert project1_nodes[0].model_dump(
        include=ProjectNodeCreate.get_field_names(exclude={"created", "modified"})
    ) == project2_nodes[0].model_dump(include=ProjectNodeCreate.get_field_names(exclude={"created", "modified"}))
    with pytest.raises(ProjectNodesNonUniqueNodeFoundError):
        await ProjectNodesRepo.get_project_id_from_node_id(asyncpg_connection, node_id=project1_nodes[0].node_id)


#
# Deadlock regression (https://github.com/ITISFoundation/private-issues/issues/669)
#
# On 2026-10-16 production raised DeadlockDetectedError on PATCH projects/{pid}/nodes/{nid}:
# a plain node update locks the node row and then, through the `projects_nodes_changed`
# trigger, the parent `projects` row; the graph mutation locks the parent row first and then
# the node row. The two orders in parallel close a cycle. All writers now take the parent row
# first (see lock_project_for_write), so both transactions must simply queue.
#

# test instrumentation only: which backend holds/waits on which lock (see the precedent in
# director-v2 test_comp_tasks_upsert_concurrency.py)
_WAITERS_BEHIND_SQL: Final[str] = (
    "SELECT count(*) FROM pg_stat_activity "
    "WHERE wait_event_type = 'Lock' AND pid <> pg_backend_pid() AND :pid = ANY(pg_blocking_pids(pid))"
)
_DEADLOCK_SQLSTATE: Final[str] = "40P01"
_TIMEOUT_S: Final[float] = 30.0


def _sqlstate(exc: BaseException) -> str | None:
    return getattr(getattr(exc, "orig", None), "sqlstate", None) or getattr(exc, "sqlstate", None)


async def _wait_until(condition: Callable[[], Awaitable[bool]], what: str) -> None:
    deadline = asyncio.get_running_loop().time() + _TIMEOUT_S
    while not await condition():  # polls the state of the database, no event to wait for
        if asyncio.get_running_loop().time() > deadline:
            pytest.fail(what)
        await asyncio.sleep(0.05)


@pytest.mark.parametrize("pg_sa_engine", ["alembicMigration"], indirect=True)
async def test_node_writes_do_not_deadlock_with_a_concurrent_parent_row_writer(
    asyncpg_engine: AsyncEngine,
    registered_project: dict[str, Any],
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
):
    """a single node update must not deadlock with a writer that locked the parent project first

    Only runs against the migrated database: the `projects_nodes_changed` trigger, which makes
    the inversion possible, is created by a migration and not by the model metadata.
    """
    project_uuid = uuid.UUID(registered_project["uuid"])
    repo = ProjectNodesRepo(project_uuid=project_uuid)
    async with asyncpg_engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        [node] = await repo.add(conn, nodes=[create_fake_projects_node()])

    node_start = asyncio.Event()

    async def _node_writer() -> None:
        # what PATCH projects/*/nodes/* does for ui/progress: a single node write whose
        # trigger touches the parent row
        await node_start.wait()
        async with asyncpg_engine.connect() as conn, conn.begin():
            await repo.update(conn, node_id=node.node_id, label="plain-update")

    node_writer: asyncio.Task[None] = asyncio.create_task(_node_writer())

    async def _parent_first_writer() -> None:
        # what the webserver graph mutation does: parent row lock (its _lock_project_graph is
        # exactly this call), then the node rows through the same repo the mutation uses
        async with asyncpg_engine.connect() as conn, conn.begin():
            assert await lock_project_for_write(conn, project_uuid)
            holder = int(await conn.scalar(sqlalchemy.text("SELECT pg_backend_pid()")))
            # the lock is held now: release the node writer, it must queue behind it
            node_start.set()

            async def _node_writer_is_done_or_behind_me() -> bool:
                if node_writer.done():
                    return True
                async with asyncpg_engine.connect() as probe:
                    return bool(
                        await probe.scalar(sqlalchemy.text(_WAITERS_BEHIND_SQL), {"pid": holder}),
                    )

            await _wait_until(
                _node_writer_is_done_or_behind_me, "the node writer neither finished nor queued behind the parent lock"
            )

            # the node row, written only after the parent row was locked first
            await repo.update(conn, node_id=node.node_id, progress=42.0)

    parent_writer: asyncio.Task[None] = asyncio.create_task(_parent_first_writer())

    # both run to completion so that a deadlock surfaces as a failure here instead of
    # cancelling the survivor
    results = await asyncio.wait_for(
        asyncio.gather(parent_writer, node_writer, return_exceptions=True), timeout=_TIMEOUT_S
    )
    failures = [result for result in results if isinstance(result, BaseException)]
    deadlock = next((exc for exc in failures if _sqlstate(exc) == _DEADLOCK_SQLSTATE), None)
    assert deadlock is None, f"deadlocked with the parent row writer: {deadlock}"
    assert not failures, f"unexpected failure: {failures}"

    async with asyncpg_engine.connect() as conn:
        final_node = await repo.get(conn, node_id=node.node_id)
    # both writers got their write in
    assert final_node.progress == pytest.approx(42.0)
    assert final_node.label == "plain-update"
