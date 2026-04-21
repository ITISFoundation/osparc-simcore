# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import asyncio
import random
import uuid
from collections.abc import Awaitable, Callable
from random import randint
from typing import Any

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
