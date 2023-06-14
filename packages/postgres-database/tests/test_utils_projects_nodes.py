# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
from typing import Any, Awaitable, Callable

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from simcore_postgres_database.utils_projects_nodes import (
    ProjectsNodeCreate,
    ProjectsNodesOperationNotAllowed,
    ProjectsNodesProjectNotFound,
    ProjectsNodesRepo,
)


@pytest.fixture
async def random_project(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
    create_fake_project: Callable[..., Awaitable[RowProxy]],
) -> dict[str, Any]:
    user = await create_fake_user(connection)
    assert user
    project = await create_fake_project(connection, user)
    assert project
    return project


@pytest.fixture
def projects_node_repo_of_invalid_project(faker: Faker) -> ProjectsNodesRepo:
    invalid_project_uuid = faker.uuid4(cast_to=None)
    repo = ProjectsNodesRepo(project_uuid=invalid_project_uuid)
    assert repo
    return repo


@pytest.fixture
def projects_node_repo(random_project: dict[str, Any]) -> ProjectsNodesRepo:
    repo = ProjectsNodesRepo(project_uuid=random_project["uuid"])
    assert repo
    return repo


async def test_create_projects_nodes_raises_if_project_not_found(
    connection: SAConnection,
    faker: Faker,
    projects_node_repo_of_invalid_project: ProjectsNodesRepo,
):
    with pytest.raises(ProjectsNodesProjectNotFound):
        await projects_node_repo_of_invalid_project.create(
            connection, node=ProjectsNodeCreate(node_id=faker.uuid4())
        )


async def test_create_projects_nodes(
    connection: SAConnection,
    faker: Faker,
    projects_node_repo: ProjectsNodesRepo,
):
    new_node = await projects_node_repo.create(
        connection, node=ProjectsNodeCreate(node_id=faker.uuid4(cast_to=None))
    )
    assert new_node


async def test_create_twice_same_projects_nodes_raises(
    connection: SAConnection,
    faker: Faker,
    projects_node_repo: ProjectsNodesRepo,
):
    new_node = await projects_node_repo.create(
        connection, node=ProjectsNodeCreate(node_id=faker.uuid4(cast_to=None))
    )

    assert new_node
    with pytest.raises(ProjectsNodesOperationNotAllowed):
        await projects_node_repo.create(
            connection, node=ProjectsNodeCreate(node_id=new_node.node_id)
        )


async def test_list_project_nodes_of_invalid_project_returns_nothing(
    connection: SAConnection,
    projects_node_repo_of_invalid_project: ProjectsNodesRepo,
):
    nodes = await projects_node_repo_of_invalid_project.list(connection)
    assert nodes == []
