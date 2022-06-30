# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=no-name-in-module
# pylint: disable=no-member
# pylint: disable=too-many-branches

import asyncio
import datetime
from pathlib import Path
from typing import Awaitable, Callable, Optional

import pytest
from aiopg.sa.engine import Engine
from faker import Faker
from models_library.api_schemas_storage import LinkType
from models_library.projects_nodes_io import SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, parse_obj_as
from pytest_simcore.helpers.utils_parametrizations import byte_size_ids
from simcore_postgres_database.storage_models import file_meta_data
from simcore_service_storage import db_file_meta_data
from simcore_service_storage.exceptions import FileMetaDataNotFoundError
from simcore_service_storage.models import S3BucketName
from simcore_service_storage.s3_client import StorageS3Client
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
def disabled_dsm_cleaner_task(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STORAGE_CLEANER_INTERVAL_S", "0")


@pytest.mark.parametrize(
    "file_size",
    [ByteSize(0), parse_obj_as(ByteSize, "10Mib"), parse_obj_as(ByteSize, "100Mib")],
    ids=byte_size_ids,
)
@pytest.mark.parametrize("link_type", [LinkType.S3, LinkType.PRESIGNED])
async def test_clean_expired_uploads_deletes_expired_pending_uploads(
    disabled_dsm_cleaner_task,
    aiopg_engine: Engine,
    simcore_s3_dsm: SimcoreS3DataManager,
    simcore_file_id: SimcoreS3FileID,
    user_id: UserID,
    link_type: LinkType,
    file_size: ByteSize,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
):
    """In this test we create valid upload links and check that once
    expired they get properly deleted"""
    await simcore_s3_dsm.create_file_upload_link(user_id, simcore_file_id, link_type)
    # ensure the database is correctly set up
    async with aiopg_engine.acquire() as conn:
        fmd = await db_file_meta_data.get(conn, simcore_file_id)
    assert fmd
    assert fmd.upload_expires_at

    # now run the cleaner, nothing should happen since the expiration was set to the default of 3600
    await simcore_s3_dsm.clean_expired_uploads()
    # check the entries are still the same
    async with aiopg_engine.acquire() as conn:
        fmd_after_clean = await db_file_meta_data.get(conn, simcore_file_id)
    assert fmd_after_clean == fmd

    # now change the upload_expires_at entry to simulate and expired entry
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            file_meta_data.update()
            .where(file_meta_data.c.file_id == simcore_file_id)
            .values(upload_expires_at=datetime.datetime.utcnow())
        )
    await asyncio.sleep(1)
    await simcore_s3_dsm.clean_expired_uploads()

    # check the entries were removed
    async with aiopg_engine.acquire() as conn:
        with pytest.raises(FileMetaDataNotFoundError):
            await db_file_meta_data.get(conn, simcore_file_id)


@pytest.mark.parametrize(
    "file_size",
    [parse_obj_as(ByteSize, "10Mib"), parse_obj_as(ByteSize, "100Mib")],
    ids=byte_size_ids,
)
@pytest.mark.parametrize("link_type", [LinkType.S3, LinkType.PRESIGNED])
async def test_clean_expired_uploads_reverts_to_last_known_version_expired_pending_uploads(
    disabled_dsm_cleaner_task,
    upload_file: Callable[
        [ByteSize, str, Optional[SimcoreS3FileID]],
        Awaitable[tuple[Path, SimcoreS3FileID]],
    ],
    aiopg_engine: Engine,
    simcore_s3_dsm: SimcoreS3DataManager,
    user_id: UserID,
    link_type: LinkType,
    file_size: ByteSize,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    faker: Faker,
):
    """In this test we first upload a file to have a valid entry, then we trigger
    a new upload of the VERY SAME FILE, expire it, and make sure the cleaner reverts
    to the last known version of the file"""
    file, file_id = await upload_file(file_size, faker.file_name(), None)
    async with aiopg_engine.acquire() as conn:
        original_fmd = await db_file_meta_data.get(conn, file_id)

    # now create a new link to the VERY SAME FILE UUID
    await simcore_s3_dsm.create_file_upload_link(user_id, file_id, link_type)
    # ensure the database is correctly set up
    async with aiopg_engine.acquire() as conn:
        fmd = await db_file_meta_data.get(conn, file_id)
    assert fmd
    assert fmd.upload_expires_at

    # now run the cleaner, nothing should happen since the expiration was set to the default of 3600
    await simcore_s3_dsm.clean_expired_uploads()
    # check the entries are still the same
    async with aiopg_engine.acquire() as conn:
        fmd_after_clean = await db_file_meta_data.get(conn, file_id)
    assert fmd_after_clean == fmd

    # now change the upload_expires_at entry to simulate an expired entry
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            file_meta_data.update()
            .where(file_meta_data.c.file_id == file_id)
            .values(upload_expires_at=datetime.datetime.utcnow())
        )
    await asyncio.sleep(1)
    await simcore_s3_dsm.clean_expired_uploads()

    # check the entries were reverted
    async with aiopg_engine.acquire() as conn:
        reverted_fmd = await db_file_meta_data.get(conn, file_id)
    assert original_fmd.dict(exclude={"created_at"}) == reverted_fmd.dict(
        exclude={"created_at"}
    )
    # check the S3 content is the old file
    s3_meta_data = await storage_s3_client.get_file_metadata(storage_s3_bucket, file_id)
    assert s3_meta_data.size == file_size
