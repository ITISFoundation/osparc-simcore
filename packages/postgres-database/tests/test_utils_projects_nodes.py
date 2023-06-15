# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
from random import randint
from typing import Any, Awaitable, Callable

import pytest
import sqlalchemy
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.utils_projects_nodes import (
    ProjectsNodeCreate,
    ProjectsNodesDuplicateNode,
    ProjectsNodesNodeNotFound,
    ProjectsNodesProjectNotFound,
    ProjectsNodesRepo,
)


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
def projects_nodes_repo_of_invalid_project(faker: Faker) -> ProjectsNodesRepo:
    invalid_project_uuid = faker.uuid4(cast_to=None)
    repo = ProjectsNodesRepo(project_uuid=invalid_project_uuid)
    assert repo
    return repo


@pytest.fixture
def projects_nodes_repo(registered_project: dict[str, Any]) -> ProjectsNodesRepo:
    repo = ProjectsNodesRepo(project_uuid=registered_project["uuid"])
    assert repo
    return repo


@pytest.fixture
def create_fake_projects_node(faker: Faker) -> Callable[..., ProjectsNodeCreate]:
    def _creator() -> ProjectsNodeCreate:
        node = ProjectsNodeCreate(node_id=faker.uuid4())
        assert node
        return node

    return _creator


async def test_create_projects_nodes_raises_if_project_not_found(
    connection: SAConnection,
    projects_nodes_repo_of_invalid_project: ProjectsNodesRepo,
    create_fake_projects_node: Callable[..., ProjectsNodeCreate],
):
    with pytest.raises(ProjectsNodesProjectNotFound):
        await projects_nodes_repo_of_invalid_project.create(
            connection, node=create_fake_projects_node()
        )


async def test_create_projects_nodes(
    connection: SAConnection,
    projects_nodes_repo: ProjectsNodesRepo,
    create_fake_projects_node: Callable[..., ProjectsNodeCreate],
):
    new_node = await projects_nodes_repo.create(
        connection, node=create_fake_projects_node()
    )
    assert new_node


async def test_create_twice_same_projects_nodes_raises(
    connection: SAConnection,
    projects_nodes_repo: ProjectsNodesRepo,
    create_fake_projects_node: Callable[..., ProjectsNodeCreate],
):
    new_node = await projects_nodes_repo.create(
        connection, node=create_fake_projects_node()
    )

    assert new_node
    with pytest.raises(ProjectsNodesDuplicateNode):
        await projects_nodes_repo.create(
            connection, node=ProjectsNodeCreate(node_id=new_node.node_id)
        )


async def test_list_project_nodes_of_invalid_project_returns_nothing(
    connection: SAConnection,
    projects_nodes_repo_of_invalid_project: ProjectsNodesRepo,
):
    nodes = await projects_nodes_repo_of_invalid_project.list(connection)
    assert nodes == []


async def test_list_project_nodes(
    connection: SAConnection,
    projects_nodes_repo: ProjectsNodesRepo,
    create_fake_projects_node: Callable[..., ProjectsNodeCreate],
):
    nodes = await projects_nodes_repo.list(connection)
    assert nodes == []

    # add some nodes
    created_nodes = [
        await projects_nodes_repo.create(connection, node=create_fake_projects_node())
        for n in range(randint(3, 12))
    ]

    nodes = await projects_nodes_repo.list(connection)
    assert nodes
    assert len(nodes) == len(created_nodes)


async def test_get_project_node_of_invalid_project_raises(
    connection: SAConnection,
    projects_nodes_repo_of_invalid_project: ProjectsNodesRepo,
    faker: Faker,
):
    with pytest.raises(ProjectsNodesNodeNotFound):
        await projects_nodes_repo_of_invalid_project.get(
            connection, node_id=faker.uuid4(cast_to=None)
        )


async def test_get_project_node_of_empty_project_raises(
    connection: SAConnection,
    projects_nodes_repo: ProjectsNodesRepo,
    faker: Faker,
):
    with pytest.raises(ProjectsNodesNodeNotFound):
        await projects_nodes_repo.get(connection, node_id=faker.uuid4(cast_to=None))


async def test_get_project_node(
    connection: SAConnection,
    projects_nodes_repo: ProjectsNodesRepo,
    create_fake_projects_node: Callable[..., ProjectsNodeCreate],
):
    new_node = await projects_nodes_repo.create(
        connection, node=create_fake_projects_node()
    )

    received_node = await projects_nodes_repo.get(connection, node_id=new_node.node_id)

    assert received_node == new_node


async def test_delete_invalid_node_does_nothing(
    connection: SAConnection,
    projects_nodes_repo_of_invalid_project: ProjectsNodesRepo,
    faker: Faker,
):
    await projects_nodes_repo_of_invalid_project.delete(
        connection, node_id=faker.uuid4(cast_to=None)
    )


async def test_delete_node(
    connection: SAConnection,
    projects_nodes_repo: ProjectsNodesRepo,
    create_fake_projects_node: Callable[..., ProjectsNodeCreate],
):
    new_node = await projects_nodes_repo.create(
        connection, node=create_fake_projects_node()
    )

    received_node = await projects_nodes_repo.get(connection, node_id=new_node.node_id)
    assert received_node == new_node
    await projects_nodes_repo.delete(connection, node_id=new_node.node_id)

    with pytest.raises(ProjectsNodesNodeNotFound):
        await projects_nodes_repo.get(connection, node_id=new_node.node_id)


async def test_share_nodes_between_projects(
    connection: SAConnection,
    registered_user: RowProxy,
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    projects_nodes_repo: ProjectsNodesRepo,
    create_fake_projects_node: Callable[..., ProjectsNodeCreate],
):
    # create a project node
    created_node = await projects_nodes_repo.create(
        connection, node=create_fake_projects_node()
    )
    assert (
        await projects_nodes_repo.get(connection, node_id=created_node.node_id)
        == created_node
    )

    # create a second project and attach the same node
    second_project = await create_fake_project(connection, registered_user)
    assert second_project
    second_projects_nodes_repo = ProjectsNodesRepo(project_uuid=second_project.uuid)
    assert second_projects_nodes_repo
    attached_node = await second_projects_nodes_repo.add(
        connection, node_id=created_node.node_id
    )
    assert attached_node
    assert attached_node == await second_projects_nodes_repo.get(
        connection, node_id=created_node.node_id
    )

    # delete the node from the first project shall not delete the node as it is in the second project
    await projects_nodes_repo.delete(connection, node_id=created_node.node_id)
    with pytest.raises(ProjectsNodesNodeNotFound):
        await projects_nodes_repo.get(connection, node_id=created_node.node_id)
    # the node is still in the second project
    received_node = await second_projects_nodes_repo.get(
        connection, node_id=created_node.node_id
    )
    assert attached_node == received_node

    # delete the node from the second project shall also delete the node
    await second_projects_nodes_repo.delete(connection, node_id=created_node.node_id)
    with pytest.raises(ProjectsNodesNodeNotFound):
        await second_projects_nodes_repo.get(connection, node_id=created_node.node_id)


async def test_delete_project_delete_all_nodes(
    connection: SAConnection,
    projects_nodes_repo: ProjectsNodesRepo,
    create_fake_projects_node: Callable[..., ProjectsNodeCreate],
):
    # create a project node
    new_node = await projects_nodes_repo.create(
        connection, node=create_fake_projects_node()
    )
    received_node = await projects_nodes_repo.get(connection, node_id=new_node.node_id)
    assert received_node == new_node

    # now delete the project from the projects table
    await connection.execute(
        sqlalchemy.delete(projects).where(
            projects.c.uuid == f"{projects_nodes_repo.project_uuid}"
        )
    )

    # the project cannot be found anymore (the link in projects_to_projects_nodes is auto-removed)
    with pytest.raises(ProjectsNodesNodeNotFound):
        await projects_nodes_repo.get(connection, node_id=new_node.node_id)

    # the underlying projects_nodes should also be gone
    # result = await connection.execute(
    #     sqlalchemy.select(projects_nodes).where(
    #         projects_nodes.c.node_id == f"{new_node.node_id}"
    #     )
    # )
    # assert result
    # row = await result.first()
    # assert row is None
