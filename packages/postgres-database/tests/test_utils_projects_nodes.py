# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import pytest
from aiopg.sa.connection import SAConnection
from faker import Faker
from simcore_postgres_database.utils_projects_nodes import (
    ProjectsNodeCreate,
    ProjectsNodesProjectNotFound,
    ProjectsNodesRepo,
)


async def test_create_projects_nodes_repo_raises_if_project_not_found(
    connection: SAConnection, faker: Faker
):
    invalid_project_uuid = faker.uuid4()
    repo = ProjectsNodesRepo(project_uuid=invalid_project_uuid)
    with pytest.raises(ProjectsNodesProjectNotFound):
        await repo.create(connection, node=ProjectsNodeCreate(node_id=faker.uuid4()))
