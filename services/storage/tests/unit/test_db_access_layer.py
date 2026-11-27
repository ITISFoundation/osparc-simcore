# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, NamedTuple
from uuid import uuid4

import pytest
import sqlalchemy as sa
from models_library.api_schemas_storage.storage_schemas import UNDEFINED_SIZE
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from pytest_simcore.helpers.storage_utils import CreateProjectAccessRightsCallable
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.workspaces import workspaces
from simcore_postgres_database.storage_models import file_meta_data
from simcore_service_storage.models import FileMetaData, FileMetaDataAtDB
from simcore_service_storage.modules.db.access_layer import (
    AccessLayerRepository,
    AccessRights,
)
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
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


@asynccontextmanager
async def _registered_directories(
    engine: AsyncEngine,
    directories: list[tuple[str, UserID]],
    *,
    project_id: ProjectID | None = None,
) -> AsyncIterator[None]:
    async with AsyncExitStack() as stack:
        for file_id, owner_id in directories:
            fmd = FileMetaData.from_simcore_node(
                user_id=owner_id,
                file_id=file_id,
                bucket="simcore-testing-bucket",
                location_id=SimcoreS3DataManager.get_location_id(),
                location_name=SimcoreS3DataManager.get_location_name(),
                sha256_checksum=None,
                file_size=UNDEFINED_SIZE,
                is_directory=True,
                project_id=f"{project_id}" if project_id else None,
            )
            await stack.enter_async_context(
                insert_and_get_row_lifespan(
                    engine,
                    table=file_meta_data,
                    values=FileMetaDataAtDB.model_validate(fmd).model_dump(),
                    pk_col=file_meta_data.c.file_id,
                )
            )
        yield


class _ApiDirectory(NamedTuple):
    directory_file_id: str  # the registered directory, as stored in file_meta_data
    file_in_directory_id: str  # a file inside it, with no entry of its own


@asynccontextmanager
async def _registered_api_directory(
    engine: AsyncEngine,
    *,
    owner_id: UserID,
    project_id: ProjectID | None = None,
    directory_suffix: str = "data",
    trailing_slash: bool = False,
) -> AsyncIterator[_ApiDirectory]:
    directory_file_id = f"api/{uuid4()}/{directory_suffix}"
    if trailing_slash:
        directory_file_id += "/"
    file_in_directory_id = f"{directory_file_id.rstrip('/')}/file.txt"

    async with _registered_directories(engine, [(directory_file_id, owner_id)], project_id=project_id):
        yield _ApiDirectory(directory_file_id=directory_file_id, file_in_directory_id=file_in_directory_id)


async def test_files_in_registered_api_directory_follow_directory_ownership(
    user_id: UserID, other_user_id: UserID, sqlalchemy_async_engine: AsyncEngine
):
    repository = AccessLayerRepository.instance(sqlalchemy_async_engine)

    async with _registered_api_directory(sqlalchemy_async_engine, owner_id=user_id) as api_directory:
        access = await repository.get_file_access_rights(user_id=user_id, file_id=api_directory.file_in_directory_id)
        assert access == AccessRights.all()

        # a foreign user must get nothing on a file inside someone else's api/ directory
        access = await repository.get_file_access_rights(
            user_id=other_user_id, file_id=api_directory.file_in_directory_id
        )
        assert access == AccessRights.none()


async def test_files_in_nested_registered_api_directory_follow_directory_ownership(
    user_id: UserID, other_user_id: UserID, sqlalchemy_async_engine: AsyncEngine
):
    # the registered directory is a nested folder, not the api/{api_dataset_id} root:
    # the ancestor lookup must reach the file's direct parent
    repository = AccessLayerRepository.instance(sqlalchemy_async_engine)

    async with _registered_api_directory(
        sqlalchemy_async_engine, owner_id=user_id, directory_suffix="data/sub"
    ) as api_directory:
        access = await repository.get_file_access_rights(user_id=user_id, file_id=api_directory.file_in_directory_id)
        assert access == AccessRights.all()

        access = await repository.get_file_access_rights(
            user_id=other_user_id, file_id=api_directory.file_in_directory_id
        )
        assert access == AccessRights.none()


async def test_api_directory_registered_with_trailing_slash_governs_files_inside_it(
    user_id: UserID, other_user_id: UserID, sqlalchemy_async_engine: AsyncEngine
):
    # a directory may be stored as `path/` (see SimcoreS3DirectoryID) or `path`
    repository = AccessLayerRepository.instance(sqlalchemy_async_engine)

    async with _registered_api_directory(
        sqlalchemy_async_engine, owner_id=user_id, trailing_slash=True
    ) as api_directory:
        access = await repository.get_file_access_rights(user_id=user_id, file_id=api_directory.file_in_directory_id)
        assert access == AccessRights.all()

        access = await repository.get_file_access_rights(
            user_id=other_user_id, file_id=api_directory.file_in_directory_id
        )
        assert access == AccessRights.none()


async def test_files_in_api_directory_governed_by_nearest_registered_directory(
    user_id: UserID, other_user_id: UserID, sqlalchemy_async_engine: AsyncEngine
):
    # other_user_id owns the outer directory, user_id the nested one: the files in the
    # nested directory must follow the nested directory, not the outer one
    api_dataset_id = f"{uuid4()}"
    outer_directory = f"api/{api_dataset_id}/data"
    inner_directory = f"{outer_directory}/sub"
    file_in_directory_id = f"{inner_directory}/file.txt"

    async with _registered_directories(
        sqlalchemy_async_engine,
        [(outer_directory, other_user_id), (inner_directory, user_id)],
    ):
        repository = AccessLayerRepository.instance(sqlalchemy_async_engine)

        access = await repository.get_file_access_rights(user_id=user_id, file_id=file_in_directory_id)
        assert access == AccessRights.all()

        access = await repository.get_file_access_rights(user_id=other_user_id, file_id=file_in_directory_id)
        assert access == AccessRights.none()


async def test_conflicting_api_directory_registrations_deny_access(
    user_id: UserID, other_user_id: UserID, sqlalchemy_async_engine: AsyncEngine
):
    # the same prefix registered twice with different owners under both stored forms
    directory_without_slash = f"api/{uuid4()}/data"
    directory_with_slash = f"{directory_without_slash}/"
    file_in_directory_id = f"{directory_with_slash}file.txt"

    async with _registered_directories(
        sqlalchemy_async_engine,
        [(directory_without_slash, user_id), (directory_with_slash, other_user_id)],
    ):
        repository = AccessLayerRepository.instance(sqlalchemy_async_engine)
        for requester in (user_id, other_user_id):
            access = await repository.get_file_access_rights(user_id=requester, file_id=file_in_directory_id)
            assert access == AccessRights.none()


async def test_api_directory_ancestor_denies_unregistered_path_with_foreign_contents(
    user_id: UserID, other_user_id: UserID, sqlalchemy_async_engine: AsyncEngine
):
    # user_id owns the registered directory, other_user_id a deeper one: the
    # unregistered path in between must not give user_id delete rights, whose
    # recursive cascade would remove other_user_id's entry
    api_dataset_id = f"{uuid4()}"
    registered_directory = f"api/{api_dataset_id}/data"
    unregistered_parent = f"{registered_directory}/mid"
    foreign_directory = f"{unregistered_parent}/sub"

    async with _registered_directories(
        sqlalchemy_async_engine,
        [(registered_directory, user_id), (foreign_directory, other_user_id)],
    ):
        repository = AccessLayerRepository.instance(sqlalchemy_async_engine)

        access = await repository.get_file_access_rights(user_id=user_id, file_id=unregistered_parent)
        assert access == AccessRights.none()

        # a path without foreign contents below stays governed by the registered directory
        access = await repository.get_file_access_rights(user_id=user_id, file_id=f"{registered_directory}/mine")
        assert access == AccessRights.all()

        # the foreign owner keeps full rights on its own registered directory
        access = await repository.get_file_access_rights(user_id=other_user_id, file_id=foreign_directory)
        assert access == AccessRights.all()


async def test_files_in_registered_api_directory_follow_project_sharing(
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
        access = await repository.get_file_access_rights(
            user_id=collaborator_id, file_id=api_directory.file_in_directory_id
        )
        assert access.read is True
        assert access.write is False


async def test_unregistered_api_directory_is_claimable_by_caller(
    other_user_id: UserID, sqlalchemy_async_engine: AsyncEngine
):
    # nothing registered anywhere under api/{api_dataset_id}: first to register owns
    repository = AccessLayerRepository.instance(sqlalchemy_async_engine)
    file_id = f"api/{uuid4()}/data/new-file.txt"
    access = await repository.get_file_access_rights(user_id=other_user_id, file_id=file_id)
    assert access == AccessRights.all()


async def test_unregistered_api_directory_with_foreign_contents_is_not_claimable(
    user_id: UserID, other_user_id: UserID, sqlalchemy_async_engine: AsyncEngine
):
    # deleting an unregistered id cascades to everything below it, so a directory
    # already populated by another user must not be claimable by the caller
    api_dataset_id = f"{uuid4()}"
    parent_directory = f"api/{api_dataset_id}/data"
    registered_subdirectory = f"{parent_directory}/sub"

    async with _registered_directories(sqlalchemy_async_engine, [(registered_subdirectory, user_id)]):
        repository = AccessLayerRepository.instance(sqlalchemy_async_engine)

        access = await repository.get_file_access_rights(user_id=other_user_id, file_id=parent_directory)
        assert access == AccessRights.none()

        # the owner can still operate on their own unregistered parent directory
        access = await repository.get_file_access_rights(user_id=user_id, file_id=parent_directory)
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
