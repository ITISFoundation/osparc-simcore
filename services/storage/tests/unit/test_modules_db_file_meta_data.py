# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import datetime
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
from uuid import uuid4

import pytest
from models_library.projects_nodes_io import SimcoreS3FileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import TypeAdapter
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from simcore_postgres_database.storage_models import file_meta_data as file_meta_data_table
from simcore_service_storage.constants import EXPORTS_S3_PREFIX
from simcore_service_storage.models import FileMetaData, FileMetaDataAtDB, S3BucketName
from simcore_service_storage.modules.db.file_meta_data import FileMetaDataRepository
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
async def create_fmd(
    sqlalchemy_async_engine: AsyncEngine,
    storage_s3_bucket: S3BucketName,
) -> AsyncIterator[Callable[..., Awaitable[SimcoreS3FileID]]]:
    """creates a file_meta_data entry directly in the DB (no S3 involved) and removes it
    once the test completes, reusing the `insert_and_get_row_lifespan` create/cleanup
    helper used across the repository for this exact pattern.
    """
    async with AsyncExitStack() as stack:

        async def _creator(*, user_id: UserID, file_id: str, created_at: datetime.datetime) -> SimcoreS3FileID:
            validated_file_id = TypeAdapter(SimcoreS3FileID).validate_python(file_id)
            fmd = FileMetaData.from_simcore_node(
                user_id=user_id,
                file_id=validated_file_id,
                bucket=storage_s3_bucket,
                location_id=SimcoreS3DataManager.get_location_id(),
                location_name=SimcoreS3DataManager.get_location_name(),
                sha256_checksum=None,
                created_at=created_at,
                last_modified=created_at,
            )
            await stack.enter_async_context(
                insert_and_get_row_lifespan(
                    sqlalchemy_async_engine,
                    table=file_meta_data_table,
                    values=jsonable_encoder(FileMetaDataAtDB.model_validate(fmd)),
                    pk_col=file_meta_data_table.c.file_id,
                )
            )
            return validated_file_id

        yield _creator


async def test_list_fmds_filters_by_file_id_prefix(
    sqlalchemy_async_engine: AsyncEngine,
    user_id: UserID,
    create_fmd: Callable[..., Awaitable[SimcoreS3FileID]],
):
    """an entry under the `exports/` prefix must be included, one outside of it must be excluded"""
    now = datetime.datetime.now(tz=datetime.UTC).replace(tzinfo=None)

    included_file_id = await create_fmd(
        user_id=user_id,
        file_id=f"{EXPORTS_S3_PREFIX}/{user_id}/{uuid4()}.zip",
        created_at=now,
    )
    excluded_file_id = await create_fmd(
        user_id=user_id,
        file_id=f"api/{uuid4()}/some_file.dat",
        created_at=now,
    )

    found = await FileMetaDataRepository.instance(sqlalchemy_async_engine).list_fmds(
        file_id_prefix=f"{EXPORTS_S3_PREFIX}/"
    )

    found_file_ids = {fmd.file_id for fmd in found}
    assert included_file_id in found_file_ids
    assert excluded_file_id not in found_file_ids


async def test_list_fmds_filters_by_created_before(
    sqlalchemy_async_engine: AsyncEngine,
    user_id: UserID,
    create_fmd: Callable[..., Awaitable[SimcoreS3FileID]],
):
    """an entry created before the threshold must be included, one created after it must be excluded"""
    now = datetime.datetime.now(tz=datetime.UTC).replace(tzinfo=None)
    threshold = now - datetime.timedelta(days=30)

    included_file_id = await create_fmd(
        user_id=user_id,
        file_id=f"{EXPORTS_S3_PREFIX}/{user_id}/{uuid4()}.zip",
        created_at=now - datetime.timedelta(days=40),
    )
    excluded_file_id = await create_fmd(
        user_id=user_id,
        file_id=f"{EXPORTS_S3_PREFIX}/{user_id}/{uuid4()}.zip",
        created_at=now - datetime.timedelta(days=5),
    )

    found = await FileMetaDataRepository.instance(sqlalchemy_async_engine).list_fmds(created_before=threshold)

    found_file_ids = {fmd.file_id for fmd in found}
    assert included_file_id in found_file_ids
    assert excluded_file_id not in found_file_ids
