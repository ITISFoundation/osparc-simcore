# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import asyncio
import random
import uuid
from random import randint
from typing import Any, Awaitable, Callable

import pytest
import sqlalchemy
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import RowProxy
from faker import Faker
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_nodes import projects_nodes
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNodeCreate,
    ProjectNodesDuplicateNode,
    ProjectNodesNodeNotFound,
    ProjectNodesProjectNotFound,
    ProjectNodesRepo,
)


async def _delete_project(connection: SAConnection, project_uuid: uuid.UUID) -> None:
    result = await connection.execute(
        sqlalchemy.delete(projects).where(projects.c.uuid == f"{project_uuid}")
    )
    assert result.rowcount == 1


@pytest.fixture
async def registered_user(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
) -> RowProxy:
    user = await create_fake_user(connection)
    assert user
    return user


@pytest.fixture
async def registered_project(
    connection: SAConnection,
    registered_user: RowProxy,
    create_fake_project: Callable[..., Awaitable[RowProxy]],
) -> dict[str, Any]:
    project = await create_fake_project(connection, registered_user)
    assert project
    return dict(project)


@pytest.fixture
def projects_nodes_repo_of_invalid_project(faker: Faker) -> ProjectNodesRepo:
    invalid_project_uuid = faker.uuid4(cast_to=None)
    repo = ProjectNodesRepo(project_uuid=invalid_project_uuid)
    assert repo
    return repo


@pytest.fixture
def projects_nodes_repo(registered_project: dict[str, Any]) -> ProjectNodesRepo:
    repo = ProjectNodesRepo(project_uuid=registered_project["uuid"])
    assert repo
    return repo


@pytest.fixture
def create_fake_projects_node(faker: Faker) -> Callable[..., ProjectNodeCreate]:
    def _creator() -> ProjectNodeCreate:
        node = ProjectNodeCreate(required_resources=faker.pydict(allowed_types=(str,)))
        assert node
        return node

    return _creator


@pytest.fixture
def create_fake_node_id(faker: Faker) -> Callable[[], uuid.UUID]:
    def _creator() -> uuid.UUID:
        return faker.uuid4(cast_to=None)

    return _creator


async def test_create_projects_nodes_raises_if_project_not_found(
    connection: SAConnection,
    projects_nodes_repo_of_invalid_project: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    create_fake_node_id: Callable[[], uuid.UUID],
):
    with pytest.raises(ProjectNodesProjectNotFound):
        await projects_nodes_repo_of_invalid_project.add(
            connection,
            node_ids=[create_fake_node_id()],
            nodes=[create_fake_projects_node()],
        )


async def test_create_projects_nodes(
    connection: SAConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    create_fake_node_id: Callable[[], uuid.UUID],
):
    new_nodes = await projects_nodes_repo.add(
        connection,
        node_ids=[create_fake_node_id()],
        nodes=[create_fake_projects_node()],
    )
    assert new_nodes
    assert len(new_nodes) == 1
    assert new_nodes[0]


async def test_create_twice_same_projects_nodes_raises(
    connection: SAConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    create_fake_node_id: Callable[[], uuid.UUID],
):
    node_id = create_fake_node_id()
    new_nodes = await projects_nodes_repo.add(
        connection, node_ids=[node_id], nodes=[create_fake_projects_node()]
    )
    assert new_nodes
    with pytest.raises(ProjectNodesDuplicateNode):
        await projects_nodes_repo.add(
            connection,
            node_ids=[node_id],
            nodes=[create_fake_projects_node()],
        )


async def test_list_project_nodes_of_invalid_project_returns_nothing(
    connection: SAConnection,
    projects_nodes_repo_of_invalid_project: ProjectNodesRepo,
):
    nodes = await projects_nodes_repo_of_invalid_project.list(connection)
    assert nodes == []


async def test_list_project_nodes(
    connection: SAConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    create_fake_node_id: Callable[[], uuid.UUID],
):
    nodes = await projects_nodes_repo.list(connection)
    assert nodes == []

    # add some nodes
    NUM_NODES = randint(3, 12)
    created_nodes = await projects_nodes_repo.add(
        connection,
        node_ids=[create_fake_node_id() for _ in range(NUM_NODES)],
        nodes=[create_fake_projects_node() for _ in range(NUM_NODES)],
    )

    nodes = await projects_nodes_repo.list(connection)
    assert nodes
    assert len(nodes) == len(created_nodes)


async def test_get_project_node_of_invalid_project_raises(
    connection: SAConnection,
    projects_nodes_repo_of_invalid_project: ProjectNodesRepo,
    create_fake_node_id: Callable[[], uuid.UUID],
):
    with pytest.raises(ProjectNodesNodeNotFound):
        await projects_nodes_repo_of_invalid_project.get(
            connection, node_id=create_fake_node_id()
        )


async def test_get_project_node_of_empty_project_raises(
    connection: SAConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_node_id: Callable[[], uuid.UUID],
):
    with pytest.raises(ProjectNodesNodeNotFound):
        await projects_nodes_repo.get(connection, node_id=create_fake_node_id())


async def test_get_project_node(
    connection: SAConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    create_fake_node_id: Callable[[], uuid.UUID],
):
    node_id = create_fake_node_id()
    new_nodes = await projects_nodes_repo.add(
        connection, node_ids=[node_id], nodes=[create_fake_projects_node()]
    )
    assert len(new_nodes) == 1
    assert new_nodes[0]

    received_node = await projects_nodes_repo.get(connection, node_id=node_id)

    assert received_node == new_nodes[0]


async def test_update_project_node_of_invalid_node_raises(
    connection: SAConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    create_fake_node_id: Callable[[], uuid.UUID],
    faker: Faker,
):
    new_nodes = await projects_nodes_repo.add(
        connection,
        node_ids=[create_fake_node_id()],
        nodes=[create_fake_projects_node()],
    )
    assert len(new_nodes) == 1
    assert new_nodes[0]
    assert new_nodes[0].created == new_nodes[0].modified
    with pytest.raises(ProjectNodesNodeNotFound):
        await projects_nodes_repo.update(
            connection,
            node_id=create_fake_node_id(),
            required_resources={faker.pystr(): faker.pyint()},
        )


async def test_update_project_node(
    connection: SAConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    create_fake_node_id: Callable[[], uuid.UUID],
    faker: Faker,
):
    node_id = create_fake_node_id()
    new_nodes = await projects_nodes_repo.add(
        connection, node_ids=[node_id], nodes=[create_fake_projects_node()]
    )
    assert len(new_nodes) == 1
    assert new_nodes[0]
    assert new_nodes[0].created == new_nodes[0].modified
    required_resources = {faker.pystr(): faker.pyint()}
    updated_node = await projects_nodes_repo.update(
        connection,
        node_id=new_nodes[0].node_id,
        required_resources=required_resources,
    )
    assert updated_node
    assert updated_node != new_nodes
    assert updated_node.modified > new_nodes[0].modified
    assert updated_node.created == new_nodes[0].created
    assert updated_node.required_resources == required_resources


async def test_delete_invalid_node_does_nothing(
    connection: SAConnection,
    projects_nodes_repo_of_invalid_project: ProjectNodesRepo,
    create_fake_node_id: Callable[[], uuid.UUID],
):
    await projects_nodes_repo_of_invalid_project.delete(
        connection, node_id=create_fake_node_id()
    )


async def test_delete_node(
    connection: SAConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    create_fake_node_id: Callable[[], uuid.UUID],
):
    new_nodes = await projects_nodes_repo.add(
        connection,
        node_ids=[create_fake_node_id()],
        nodes=[create_fake_projects_node()],
    )
    assert len(new_nodes) == 1
    assert new_nodes[0]

    received_node = await projects_nodes_repo.get(
        connection, node_id=new_nodes[0].node_id
    )
    assert received_node == new_nodes[0]
    await projects_nodes_repo.delete(connection, node_id=new_nodes[0].node_id)

    with pytest.raises(ProjectNodesNodeNotFound):
        await projects_nodes_repo.get(connection, node_id=new_nodes[0].node_id)


async def test_delete_project_delete_all_nodes(
    connection: SAConnection,
    projects_nodes_repo: ProjectNodesRepo,
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    create_fake_node_id: Callable[[], uuid.UUID],
):
    # create a project node
    new_nodes = await projects_nodes_repo.add(
        connection,
        node_ids=[create_fake_node_id()],
        nodes=[create_fake_projects_node()],
    )
    assert len(new_nodes) == 1
    assert new_nodes[0]
    received_node = await projects_nodes_repo.get(
        connection, node_id=new_nodes[0].node_id
    )
    assert received_node == new_nodes[0]

    # now delete the project from the projects table
    await _delete_project(connection, projects_nodes_repo.project_uuid)

    # the project cannot be found anymore (the link in projects_to_projects_nodes is auto-removed)
    with pytest.raises(ProjectNodesNodeNotFound):
        await projects_nodes_repo.get(connection, node_id=new_nodes[0].node_id)

    # the underlying projects_nodes should also be gone, thanks to migration
    result = await connection.execute(
        sqlalchemy.select(projects_nodes).where(
            projects_nodes.c.node_id == f"{new_nodes[0].node_id}"
        )
    )
    assert result
    row = await result.first()
    assert row is None


@pytest.mark.parametrize("num_concurrent_workflows", [1, 250])
async def test_multiple_creation_deletion_of_nodes(
    pg_engine: Engine,
    registered_user: RowProxy,
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    create_fake_projects_node: Callable[..., ProjectNodeCreate],
    create_fake_node_id: Callable[[], uuid.UUID],
    num_concurrent_workflows: int,
):
    NUM_NODES = 11

    async def _workflow() -> None:
        async with pg_engine.acquire() as connection:
            project = await create_fake_project(connection, registered_user)
            projects_nodes_repo = ProjectNodesRepo(project_uuid=project.uuid)

            await projects_nodes_repo.add(
                connection,
                node_ids=[create_fake_node_id() for _ in range(NUM_NODES)],
                nodes=[create_fake_projects_node() for _ in range(NUM_NODES)],
            )
            list_nodes = await projects_nodes_repo.list(connection)
            assert list_nodes
            assert len(list_nodes) == NUM_NODES
            await projects_nodes_repo.delete(
                connection, node_id=random.choice(list_nodes).node_id
            )
            list_nodes = await projects_nodes_repo.list(connection)
            assert list_nodes
            assert len(list_nodes) == (NUM_NODES - 1)
            await _delete_project(connection, project_uuid=project.uuid)

    await asyncio.gather(*(_workflow() for _ in range(num_concurrent_workflows)))
