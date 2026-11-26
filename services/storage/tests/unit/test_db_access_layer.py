# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, NamedTuple
from uuid import uuid4

import pytest
import sqlalchemy as sa
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_simcore.helpers.storage_utils import CreateProjectAccessRightsCallable
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.workspaces import workspaces
from simcore_postgres_database.storage_models import file_meta_data
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


async def _insert_fmd(
    engine: AsyncEngine,
    *,
    file_id: str,
    user_id: UserID,
    is_directory: bool,
    project_id: str | None = None,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            file_meta_data.insert().values(
                location_id="0",
                location="simcore.s3",
                bucket_name="simcore-testing-bucket",
                object_name=file_id,
                project_id=project_id,
                user_id=user_id,
                file_id=file_id,
                file_size=1024 if not is_directory else None,
                created_at=sa.func.now(),
                last_modified=sa.func.now(),
                is_directory=is_directory,
            )
        )


class _RegisteredApiDirectory(NamedTuple):
    directory_file_id: str
    child_file_id: str


@asynccontextmanager
async def _registered_api_directory(
    engine: AsyncEngine,
    *,
    owner_id: UserID,
    project_id: ProjectID | None = None,
    directory_suffix: str = "data",
) -> AsyncIterator[_RegisteredApiDirectory]:
    api_file_id = f"{uuid4()}"
    directory_file_id = f"api/{api_file_id}/{directory_suffix}"
    child_file_id = f"{directory_file_id}/secret.csv"
    await _insert_fmd(
        engine,
        file_id=directory_file_id,
        user_id=owner_id,
        is_directory=True,
        project_id=f"{project_id}" if project_id else None,
    )
    try:
        # the child has no entry of its own: that is the layout of a synced directory
        yield _RegisteredApiDirectory(directory_file_id=directory_file_id, child_file_id=child_file_id)
    finally:
        async with engine.begin() as conn:
            await conn.execute(file_meta_data.delete().where(file_meta_data.c.file_id == directory_file_id))


async def test_api_directory_children_follow_directory_ownership(
    user_id: UserID, other_user_id: UserID, sqlalchemy_async_engine: AsyncEngine
):
    repository = AccessLayerRepository.instance(sqlalchemy_async_engine)

    async with _registered_api_directory(sqlalchemy_async_engine, owner_id=user_id) as api_directory:
        access = await repository.get_file_access_rights(user_id=user_id, file_id=api_directory.child_file_id)
        assert access == AccessRights.all()

        # a foreign user must get nothing on a child of someone else's api/ directory
        access = await repository.get_file_access_rights(user_id=other_user_id, file_id=api_directory.child_file_id)
        assert access == AccessRights.none()


async def test_api_subdirectory_children_follow_directory_ownership(
    user_id: UserID, other_user_id: UserID, sqlalchemy_async_engine: AsyncEngine
):
    # the registered directory is a sub-folder, not the api/{file_id} root:
    # the ancestor scan must reach the child's direct parent
    repository = AccessLayerRepository.instance(sqlalchemy_async_engine)

    async with _registered_api_directory(
        sqlalchemy_async_engine, owner_id=user_id, directory_suffix="data/sub"
    ) as api_directory:
        access = await repository.get_file_access_rights(user_id=user_id, file_id=api_directory.child_file_id)
        assert access == AccessRights.all()

        access = await repository.get_file_access_rights(user_id=other_user_id, file_id=api_directory.child_file_id)
        assert access == AccessRights.none()


async def test_api_directory_children_follow_project_sharing(
    user_id: UserID,
    collaborator_id: UserID,
    project_id: ProjectID,
    create_project_access_rights: CreateProjectAccessRightsCallable,
    sqlalchemy_async_engine: AsyncEngine,
):
    await create_project_access_rights(
        project_id=project_id, user_id=collaborator_id, read=True, write=False, delete=False
    )

    repository = AccessLayerRepository.instance(sqlalchemy_async_engine)
    async with _registered_api_directory(
        sqlalchemy_async_engine, owner_id=user_id, project_id=project_id
    ) as api_directory:
        access = await repository.get_file_access_rights(user_id=collaborator_id, file_id=api_directory.child_file_id)
        assert access.read is True
        assert access.write is False


async def test_unregistered_api_directory_is_claimable_by_caller(
    other_user_id: UserID, sqlalchemy_async_engine: AsyncEngine
):
    # nothing registered anywhere under api/{file_id}: first to register owns
    repository = AccessLayerRepository.instance(sqlalchemy_async_engine)
    file_id = f"api/{uuid4()}/data/new-file.txt"
    access = await repository.get_file_access_rights(user_id=other_user_id, file_id=file_id)
    assert access == AccessRights.all()


async def test_exports_file_access_bound_to_owner(
    user_id: UserID, other_user_id: UserID, sqlalchemy_async_engine: AsyncEngine
):
    repository = AccessLayerRepository.instance(sqlalchemy_async_engine)

    own_export = f"exports/{user_id}/{uuid4()}.zip"
    access = await repository.get_file_access_rights(user_id=user_id, file_id=own_export)
    assert access == AccessRights.all()

    foreign_export = f"exports/{other_user_id}/{uuid4()}.zip"
    access = await repository.get_file_access_rights(user_id=user_id, file_id=foreign_export)
    assert access == AccessRights.none()


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
