# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
import sqlalchemy as sa
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.workspaces import workspaces
from simcore_service_storage.modules.db.access_layer import (
    AccessLayerRepository,
    AccessRights,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_access_rights_on_owned_project(
    user_id: UserID, project_id: ProjectID, sqlalchemy_async_engine: AsyncEngine
):
    access = await AccessLayerRepository.instance(sqlalchemy_async_engine).get_project_access_rights(
        user_id=user_id, project_id=project_id
    )
    assert access == AccessRights.all()

    # still NOT registered in file_meta_data BUT with prefix {project_id} owned by user
    access = await AccessLayerRepository.instance(sqlalchemy_async_engine).get_file_access_rights(
        user_id=user_id,
        file_id=f"{project_id}/node_id/not-in-file-metadata-table.txt",
    )
    assert access == AccessRights.all()


@pytest.fixture
async def prepare_db(user_id: UserID, project_id: ProjectID, sqlalchemy_async_engine: AsyncEngine):
    async with sqlalchemy_async_engine.connect() as conn:
        result = await conn.execute(sa.select(users.c.primary_gid).where(users.c.id == user_id))
        row = result.one()
        user_primary_id = row[0]

        result = await conn.execute(
            workspaces.insert()
            .values(
                name="test",
                description=None,
                owner_primary_gid=user_primary_id,
                thumbnail=None,
                created=sa.func.now(),
                modified=sa.func.now(),
                product_name="osparc",
            )
            .returning(workspaces.c.workspace_id)
        )
        row = result.one()
        workspace_id = row[0]

        await conn.execute(
            projects.update().values(workspace_id=workspace_id).where(projects.c.uuid == f"{project_id}")
        )

        yield

        await conn.execute(workspaces.delete())


async def test_access_rights_based_on_workspace(
    user_id: UserID,
    project_id: ProjectID,
    sqlalchemy_async_engine: AsyncEngine,
    prepare_db,
):
    access = await AccessLayerRepository.instance(sqlalchemy_async_engine).get_project_access_rights(
        user_id=user_id, project_id=project_id
    )
    assert access == AccessRights.all()

    # still NOT registered in file_meta_data BUT with prefix {project_id} owned by user
    access = await AccessLayerRepository.instance(sqlalchemy_async_engine).get_file_access_rights(
        user_id=user_id, file_id=f"{project_id}/node_id/not-in-file-metadata-table.txt"
    )
    assert access == AccessRights.all()


async def test_get_readable_project_ids_private_workspace(
    user_id: UserID,
    project_id: ProjectID,
    product_name: ProductName,
    sqlalchemy_async_engine: AsyncEngine,
):
    readable = await AccessLayerRepository.instance(sqlalchemy_async_engine).get_readable_project_ids(
        user_id=user_id, product_name=product_name
    )
    assert project_id in readable


async def test_get_readable_project_ids_shared_workspace(
    user_id: UserID,
    project_id: ProjectID,
    product_name: ProductName,
    sqlalchemy_async_engine: AsyncEngine,
    prepare_db,
):
    readable = await AccessLayerRepository.instance(sqlalchemy_async_engine).get_readable_project_ids(
        user_id=user_id, product_name=product_name
    )
    assert project_id in readable


async def test_get_readable_project_ids_no_access(
    user_id: UserID,
    project_id: ProjectID,
    product_name: ProductName,
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    sqlalchemy_async_engine: AsyncEngine,
):
    # Create a second project owned by same user (readable)
    other_project = await create_project()
    other_project_id = ProjectID(other_project["uuid"])

    readable = await AccessLayerRepository.instance(sqlalchemy_async_engine).get_readable_project_ids(
        user_id=user_id, product_name=product_name
    )
    assert project_id in readable
    assert other_project_id in readable

    # Revoke read access on the first project by removing all project_to_groups entries
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(project_to_groups.delete().where(project_to_groups.c.project_uuid == f"{project_id}"))

    readable = await AccessLayerRepository.instance(sqlalchemy_async_engine).get_readable_project_ids(
        user_id=user_id, product_name=product_name
    )
    assert project_id not in readable
    assert other_project_id in readable
