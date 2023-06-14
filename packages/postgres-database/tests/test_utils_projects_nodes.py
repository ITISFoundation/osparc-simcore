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


async def test_create_projects_nodes_raises_if_project_not_found(
    connection: SAConnection, faker: Faker
):
    invalid_project_uuid = faker.uuid4()
    repo = ProjectsNodesRepo(project_uuid=invalid_project_uuid)
    with pytest.raises(ProjectsNodesProjectNotFound):
        await repo.create(connection, node=ProjectsNodeCreate(node_id=faker.uuid4()))


async def test_create_projects_nodes(
    connection: SAConnection,
    faker: Faker,
    random_project: dict[str, Any],
):
    repo = ProjectsNodesRepo(project_uuid=random_project["uuid"])
    new_node = await repo.create(
        connection, node=ProjectsNodeCreate(node_id=faker.uuid4())
    )
    assert new_node
