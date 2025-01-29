# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
import sqlalchemy as sa
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.workspaces import workspaces
from simcore_service_storage.modules.db.access_layer import (
    AccessRights,
    get_file_access_rights,
    get_project_access_rights,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_access_rights_on_owned_project(
    user_id: UserID, project_id: ProjectID, sqlalchemy_async_engine: AsyncEngine
):
    async with sqlalchemy_async_engine.connect() as conn:
        access = await get_project_access_rights(conn, user_id, project_id)
        assert access == AccessRights.all()

        # still NOT registered in file_meta_data BUT with prefix {project_id} owned by user
        access = await get_file_access_rights(
            conn, user_id, f"{project_id}/node_id/not-in-file-metadata-table.txt"
        )
        assert access == AccessRights.all()


@pytest.fixture
async def prepare_db(
    user_id: UserID, project_id: ProjectID, sqlalchemy_async_engine: AsyncEngine
):
    async with sqlalchemy_async_engine.connect() as conn:
        result = await conn.execute(
            sa.select(users.c.primary_gid).where(users.c.id == user_id)
        )
        row = result.first()
        assert row
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
        row = result.first()
        assert row
        workspace_id = row[0]

        await conn.execute(
            projects.update()
            .values(workspace_id=workspace_id)
            .where(projects.c.uuid == f"{project_id}")
        )

        yield

        await conn.execute(workspaces.delete())


async def test_access_rights_based_on_workspace(
    user_id: UserID,
    project_id: ProjectID,
    sqlalchemy_async_engine: AsyncEngine,
    prepare_db,
):
    async with sqlalchemy_async_engine.connect() as conn:
        access = await get_project_access_rights(conn, user_id, project_id)
        assert access == AccessRights.all()

        # still NOT registered in file_meta_data BUT with prefix {project_id} owned by user
        access = await get_file_access_rights(
            conn, user_id, f"{project_id}/node_id/not-in-file-metadata-table.txt"
        )
        assert access == AccessRights.all()
