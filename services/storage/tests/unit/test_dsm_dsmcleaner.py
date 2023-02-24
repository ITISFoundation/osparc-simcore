# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=no-name-in-module
# pylint: disable=no-member
# pylint: disable=too-many-branches

import asyncio
import urllib.parse
from datetime import datetime, timedelta, timezone
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
from simcore_service_storage.models import FileMetaData, S3BucketName
from simcore_service_storage.s3_client import StorageS3Client
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
def disabled_dsm_cleaner_task(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STORAGE_CLEANER_INTERVAL_S", "0")


async def test_clean_expired_uploads_aborts_dangling_multipart_uploads(
    disabled_dsm_cleaner_task,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    simcore_s3_dsm: SimcoreS3DataManager,
    faker: Faker,
):
    """in this test we create a purely dangling multipart upload with no correspongin
    entry in file_metadata table
    """
    file_id = faker.file_name()
    file_size = parse_obj_as(ByteSize, "100Mib")
    upload_links = await storage_s3_client.create_multipart_upload_links(
        storage_s3_bucket, file_id, file_size, expiration_secs=3600
    )

    # ensure we have now an upload id
    all_ongoing_uploads = await storage_s3_client.list_ongoing_multipart_uploads(
        storage_s3_bucket
    )
    assert len(all_ongoing_uploads) == 1
    ongoing_upload_id, ongoing_file_id = all_ongoing_uploads[0]
    assert upload_links.upload_id == ongoing_upload_id
    assert ongoing_file_id == file_id

    # now run the cleaner
    await simcore_s3_dsm.clean_expired_uploads()

    # since there is no entry in the db, this upload shall be cleaned up
    assert not await storage_s3_client.list_ongoing_multipart_uploads(storage_s3_bucket)


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
    await simcore_s3_dsm.create_file_upload_links(
        user_id, simcore_file_id, link_type, file_size
    )
    # ensure the database is correctly set up
    async with aiopg_engine.acquire() as conn:
        fmd = await db_file_meta_data.get(conn, simcore_file_id)
    assert fmd
    assert fmd.upload_expires_at
    # ensure we have now an upload id IF the link was presigned ONLY
    # NOTE: S3 uploads might create multipart uploads out of storage!!
    ongoing_uploads = await storage_s3_client.list_ongoing_multipart_uploads(
        storage_s3_bucket
    )
    if fmd.upload_id and link_type == LinkType.PRESIGNED:
        assert len(ongoing_uploads) == 1
    else:
        assert not ongoing_uploads
    # now run the cleaner, nothing should happen since the expiration was set to the default of 3600
    await simcore_s3_dsm.clean_expired_uploads()
    # check the entries are still the same
    async with aiopg_engine.acquire() as conn:
        fmd_after_clean = await db_file_meta_data.get(conn, simcore_file_id)
    assert fmd_after_clean == fmd
    assert (
        await storage_s3_client.list_ongoing_multipart_uploads(storage_s3_bucket)
        == ongoing_uploads
    )

    # now change the upload_expires_at entry to simulate and expired entry
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            file_meta_data.update()
            .where(file_meta_data.c.file_id == simcore_file_id)
            .values(upload_expires_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )
    await asyncio.sleep(1)
    await simcore_s3_dsm.clean_expired_uploads()

    # check the entries were removed
    async with aiopg_engine.acquire() as conn:
        with pytest.raises(FileMetaDataNotFoundError):
            await db_file_meta_data.get(conn, simcore_file_id)
    # since there is no entry in the db, this upload shall be cleaned up
    assert not await storage_s3_client.list_ongoing_multipart_uploads(storage_s3_bucket)


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
    await simcore_s3_dsm.create_file_upload_links(
        user_id, file_id, link_type, file_size
    )
    # ensure the database is correctly set up
    async with aiopg_engine.acquire() as conn:
        fmd = await db_file_meta_data.get(conn, file_id)
    assert fmd
    assert fmd.upload_expires_at
    # ensure we have now an upload id IF the link was presigned ONLY
    # NOTE: S3 uploads might create multipart uploads out of storage!!
    ongoing_uploads = await storage_s3_client.list_ongoing_multipart_uploads(
        storage_s3_bucket
    )
    if fmd.upload_id and link_type == LinkType.PRESIGNED:
        assert len(ongoing_uploads) == 1
    else:
        assert not ongoing_uploads
    # now run the cleaner, nothing should happen since the expiration was set to the default of 3600
    await simcore_s3_dsm.clean_expired_uploads()
    # check the entries are still the same
    async with aiopg_engine.acquire() as conn:
        fmd_after_clean = await db_file_meta_data.get(conn, file_id)
    assert fmd_after_clean == fmd
    assert (
        await storage_s3_client.list_ongoing_multipart_uploads(storage_s3_bucket)
        == ongoing_uploads
    )

    # now change the upload_expires_at entry to simulate an expired entry
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            file_meta_data.update()
            .where(file_meta_data.c.file_id == file_id)
            .values(upload_expires_at=datetime.now(timezone.utc).replace(tzinfo=None))
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
    # since there is no entry in the db, this upload shall be cleaned up
    assert not await storage_s3_client.list_ongoing_multipart_uploads(storage_s3_bucket)


@pytest.mark.parametrize(
    "file_size",
    [parse_obj_as(ByteSize, "100Mib")],
    ids=byte_size_ids,
)
async def test_clean_expired_uploads_does_not_clean_multipart_upload_on_creation(
    disabled_dsm_cleaner_task,
    aiopg_engine: Engine,
    simcore_s3_dsm: SimcoreS3DataManager,
    simcore_file_id: SimcoreS3FileID,
    user_id: UserID,
    file_size: ByteSize,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
):
    """This test reproduces what create_file_upload_links in dsm does, but running
    the cleaner in between to ensure the cleaner does not break the mechanism"""
    later_than_now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        minutes=5
    )
    fmd = FileMetaData.from_simcore_node(
        user_id,
        simcore_file_id,
        storage_s3_bucket,
        simcore_s3_dsm.location_id,
        simcore_s3_dsm.location_name,
        upload_expires_at=later_than_now,
    )
    # we create the entry in the db
    async with aiopg_engine.acquire() as conn:
        await db_file_meta_data.upsert(conn, fmd)

        # ensure the database is correctly set up
        fmd_in_db = await db_file_meta_data.get(conn, simcore_file_id)
    assert fmd_in_db
    assert fmd_in_db.upload_expires_at
    # we create the multipart upload link
    upload_links = await storage_s3_client.create_multipart_upload_links(
        storage_s3_bucket, simcore_file_id, file_size, expiration_secs=3600
    )

    # ensure we have now an upload id
    all_ongoing_uploads = await storage_s3_client.list_ongoing_multipart_uploads(
        storage_s3_bucket
    )
    assert len(all_ongoing_uploads) == 1
    ongoing_upload_id, ongoing_file_id = all_ongoing_uploads[0]
    assert upload_links.upload_id == ongoing_upload_id
    assert urllib.parse.unquote(ongoing_file_id) == simcore_file_id

    # now cleanup, we do not have an explicit upload_id in the database yet
    await simcore_s3_dsm.clean_expired_uploads()

    # ensure we STILL have the same upload id
    all_ongoing_uploads_after_clean = (
        await storage_s3_client.list_ongoing_multipart_uploads(storage_s3_bucket)
    )
    assert len(all_ongoing_uploads_after_clean) == 1
    assert all_ongoing_uploads == all_ongoing_uploads_after_clean


@pytest.mark.parametrize(
    "file_size",
    [parse_obj_as(ByteSize, "100Mib")],
    ids=byte_size_ids,
)
async def test_clean_expired_uploads_cleans_dangling_multipart_uploads_if_no_corresponding_upload_found(
    disabled_dsm_cleaner_task,
    aiopg_engine: Engine,
    simcore_s3_dsm: SimcoreS3DataManager,
    simcore_file_id: SimcoreS3FileID,
    user_id: UserID,
    file_size: ByteSize,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
):
    """This test reproduces what create_file_upload_links in dsm does, but running
    the cleaner in between to ensure the cleaner does not break the mechanism"""
    later_than_now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        minutes=5
    )
    fmd = FileMetaData.from_simcore_node(
        user_id,
        simcore_file_id,
        storage_s3_bucket,
        simcore_s3_dsm.location_id,
        simcore_s3_dsm.location_name,
        upload_expires_at=later_than_now,
    )
    # we create the entry in the db
    async with aiopg_engine.acquire() as conn:
        await db_file_meta_data.upsert(conn, fmd)

        # ensure the database is correctly set up
        fmd_in_db = await db_file_meta_data.get(conn, simcore_file_id)
    assert fmd_in_db
    assert fmd_in_db.upload_expires_at
    # we create the multipart upload link
    upload_links = await storage_s3_client.create_multipart_upload_links(
        storage_s3_bucket, simcore_file_id, file_size, expiration_secs=3600
    )

    # ensure we have now an upload id
    all_ongoing_uploads = await storage_s3_client.list_ongoing_multipart_uploads(
        storage_s3_bucket
    )
    assert len(all_ongoing_uploads) == 1
    ongoing_upload_id, ongoing_file_id = all_ongoing_uploads[0]
    assert upload_links.upload_id == ongoing_upload_id
    assert urllib.parse.unquote(ongoing_file_id) == simcore_file_id

    # now cleanup, we do not have an explicit upload_id in the database yet
    await simcore_s3_dsm.clean_expired_uploads()

    # ensure we STILL have the same upload id
    all_ongoing_uploads_after_clean = (
        await storage_s3_client.list_ongoing_multipart_uploads(storage_s3_bucket)
    )
    assert len(all_ongoing_uploads_after_clean) == 1
    assert all_ongoing_uploads == all_ongoing_uploads_after_clean
