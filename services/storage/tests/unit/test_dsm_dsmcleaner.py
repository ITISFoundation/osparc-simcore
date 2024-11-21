# pylint: disable=no-member
# pylint: disable=no-name-in-module
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import datetime
import urllib.parse
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Final

import arrow
import pytest
from aiopg.sa.engine import Engine
from aws_library.s3 import MultiPartUploadLinks, SimcoreS3API
from faker import Faker
from models_library.api_schemas_storage import LinkType
from models_library.basic_types import SHA256Str
from models_library.projects_nodes_io import SimcoreS3DirectoryID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.parametrizations import byte_size_ids
from simcore_postgres_database.storage_models import file_meta_data
from simcore_service_storage import db_file_meta_data
from simcore_service_storage.exceptions import (
    FileAccessRightError,
    FileMetaDataNotFoundError,
)
from simcore_service_storage.models import FileMetaData, S3BucketName, UploadID
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]

_faker: Faker = Faker()


@pytest.fixture
def disabled_dsm_cleaner_task(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STORAGE_CLEANER_INTERVAL_S", "0")


@pytest.fixture
def simcore_directory_id(simcore_file_id: SimcoreS3FileID) -> SimcoreS3FileID:
    return TypeAdapter(SimcoreS3FileID).validate_python(
        SimcoreS3DirectoryID.from_simcore_s3_object(simcore_file_id)
    )


@pytest.mark.parametrize(
    "file_size",
    [
        TypeAdapter(ByteSize).validate_python("0"),
        TypeAdapter(ByteSize).validate_python("10Mib"),
        TypeAdapter(ByteSize).validate_python("100Mib"),
    ],
    ids=byte_size_ids,
)
@pytest.mark.parametrize(
    "link_type, is_directory",
    [
        # NOTE: directories are handled only as LinkType.S3
        (LinkType.S3, True),
        (LinkType.S3, False),
        (LinkType.PRESIGNED, False),
    ],
)
@pytest.mark.parametrize("checksum", [None, _faker.sha256()])
async def test_regression_collaborator_creates_file_upload_links(  # pylint:disable=too-many-positional-arguments
    disabled_dsm_cleaner_task,
    aiopg_engine: Engine,
    simcore_s3_dsm: SimcoreS3DataManager,
    simcore_file_id: SimcoreS3FileID,
    simcore_directory_id: SimcoreS3FileID,
    user_id: UserID,
    link_type: LinkType,
    file_size: ByteSize,
    is_directory: bool,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    checksum: SHA256Str | None,
    collaborator_id: UserID,
    share_with_collaborator: Callable[[], Awaitable[None]],
):
    file_or_directory_id = simcore_directory_id if is_directory else simcore_file_id

    await simcore_s3_dsm.create_file_upload_links(
        user_id,
        file_or_directory_id,
        link_type,
        file_size,
        sha256_checksum=checksum,
        is_directory=is_directory,
    )

    # collaborators don't have access
    with pytest.raises(FileAccessRightError):
        await simcore_s3_dsm.create_file_upload_links(
            collaborator_id,
            file_or_directory_id,
            link_type,
            file_size,
            sha256_checksum=checksum,
            is_directory=is_directory,
        )

    await share_with_collaborator()

    # collaborator have access
    await simcore_s3_dsm.create_file_upload_links(
        collaborator_id,
        file_or_directory_id,
        link_type,
        file_size,
        sha256_checksum=checksum,
        is_directory=is_directory,
    )


@pytest.mark.parametrize(
    "file_size",
    [
        ByteSize(0),
        TypeAdapter(ByteSize).validate_python("10Mib"),
        TypeAdapter(ByteSize).validate_python("100Mib"),
    ],
    ids=byte_size_ids,
)
@pytest.mark.parametrize(
    "link_type, is_directory",
    [
        # NOTE: directories are handled only as LinkType.S3
        (LinkType.S3, True),
        (LinkType.S3, False),
        (LinkType.PRESIGNED, False),
    ],
)
@pytest.mark.parametrize("checksum", [None, _faker.sha256()])
async def test_clean_expired_uploads_deletes_expired_pending_uploads(
    disabled_dsm_cleaner_task,
    aiopg_engine: Engine,
    simcore_s3_dsm: SimcoreS3DataManager,
    simcore_file_id: SimcoreS3FileID,
    simcore_directory_id: SimcoreS3FileID,
    user_id: UserID,
    link_type: LinkType,
    file_size: ByteSize,
    is_directory: bool,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    checksum: SHA256Str | None,
):
    """In this test we create valid upload links and check that once
    expired they get properly deleted"""

    file_or_directory_id = simcore_directory_id if is_directory else simcore_file_id

    await simcore_s3_dsm.create_file_upload_links(
        user_id,
        file_or_directory_id,
        link_type,
        file_size,
        sha256_checksum=checksum,
        is_directory=is_directory,
    )
    # ensure the database is correctly set up
    async with aiopg_engine.acquire() as conn:
        fmd = await db_file_meta_data.get(conn, file_or_directory_id)
    assert fmd
    assert fmd.upload_expires_at
    # ensure we have now an upload id IF the link was presigned ONLY
    # NOTE: S3 uploads might create multipart uploads out of storage!!
    ongoing_uploads = await storage_s3_client.list_ongoing_multipart_uploads(
        bucket=storage_s3_bucket
    )
    if fmd.upload_id and link_type == LinkType.PRESIGNED:
        assert len(ongoing_uploads) == 1
    else:
        assert not ongoing_uploads
    # now run the cleaner, nothing should happen since the expiration was set to the default of 3600
    await simcore_s3_dsm.clean_expired_uploads()
    # check the entries are still the same
    async with aiopg_engine.acquire() as conn:
        fmd_after_clean = await db_file_meta_data.get(conn, file_or_directory_id)
    assert fmd_after_clean == fmd
    assert (
        await storage_s3_client.list_ongoing_multipart_uploads(bucket=storage_s3_bucket)
        == ongoing_uploads
    )

    # now change the upload_expires_at entry to simulate and expired entry
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            file_meta_data.update()
            .where(file_meta_data.c.file_id == file_or_directory_id)
            .values(upload_expires_at=arrow.utcnow().datetime)
        )
    await asyncio.sleep(1)
    await simcore_s3_dsm.clean_expired_uploads()

    # check the entries were removed
    async with aiopg_engine.acquire() as conn:
        with pytest.raises(FileMetaDataNotFoundError):
            await db_file_meta_data.get(conn, simcore_file_id)
    # since there is no entry in the db, this upload shall be cleaned up
    assert not await storage_s3_client.list_ongoing_multipart_uploads(
        bucket=storage_s3_bucket
    )


@pytest.mark.parametrize(
    "file_size",
    [
        TypeAdapter(ByteSize).validate_python("10Mib"),
        TypeAdapter(ByteSize).validate_python("100Mib"),
    ],
    ids=byte_size_ids,
)
@pytest.mark.parametrize("link_type", [LinkType.S3, LinkType.PRESIGNED])
@pytest.mark.parametrize("checksum", [_faker.sha256(), None])
async def test_clean_expired_uploads_reverts_to_last_known_version_expired_pending_uploads(
    disabled_dsm_cleaner_task,
    upload_file: Callable[
        ...,
        Awaitable[tuple[Path, SimcoreS3FileID]],
    ],
    aiopg_engine: Engine,
    simcore_s3_dsm: SimcoreS3DataManager,
    user_id: UserID,
    link_type: LinkType,
    file_size: ByteSize,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    with_versioning_enabled: None,
    checksum: SHA256Str | None,
):
    """In this test we first upload a file to have a valid entry, then we trigger
    a new upload of the VERY SAME FILE, expire it, and make sure the cleaner reverts
    to the last known version of the file"""
    file, file_id = await upload_file(
        file_size=file_size,
        file_name=_faker.file_name(),
        file_id=None,
        sha256_checksum=checksum,
    )
    async with aiopg_engine.acquire() as conn:
        original_fmd = await db_file_meta_data.get(conn, file_id)

    # now create a new link to the VERY SAME FILE UUID
    await simcore_s3_dsm.create_file_upload_links(
        user_id,
        file_id,
        link_type,
        file_size,
        sha256_checksum=checksum,
        is_directory=False,
    )
    # ensure the database is correctly set up
    async with aiopg_engine.acquire() as conn:
        fmd = await db_file_meta_data.get(conn, file_id)
    assert fmd
    assert fmd.upload_expires_at
    # ensure we have now an upload id IF the link was presigned ONLY
    # NOTE: S3 uploads might create multipart uploads out of storage!!
    ongoing_uploads = await storage_s3_client.list_ongoing_multipart_uploads(
        bucket=storage_s3_bucket
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
        await storage_s3_client.list_ongoing_multipart_uploads(bucket=storage_s3_bucket)
        == ongoing_uploads
    )

    # now change the upload_expires_at entry to simulate an expired entry
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            file_meta_data.update()
            .where(file_meta_data.c.file_id == file_id)
            .values(upload_expires_at=arrow.utcnow().datetime)
        )
    await asyncio.sleep(1)
    await simcore_s3_dsm.clean_expired_uploads()

    # check the entries were reverted
    async with aiopg_engine.acquire() as conn:
        reverted_fmd = await db_file_meta_data.get(conn, file_id)
    assert original_fmd.model_dump(exclude={"created_at"}) == reverted_fmd.model_dump(
        exclude={"created_at"}
    )
    # check the S3 content is the old file
    s3_meta_data = await storage_s3_client.get_object_metadata(
        bucket=storage_s3_bucket, object_key=file_id
    )
    assert s3_meta_data.size == file_size
    # since there is no entry in the db, this upload shall be cleaned up
    assert not await storage_s3_client.list_ongoing_multipart_uploads(
        bucket=storage_s3_bucket
    )


@pytest.mark.parametrize(
    "file_size",
    [TypeAdapter(ByteSize).validate_python("100Mib")],
    ids=byte_size_ids,
)
@pytest.mark.parametrize("is_directory", [True, False])
@pytest.mark.parametrize("checksum", [_faker.sha256(), None])
async def test_clean_expired_uploads_does_not_clean_multipart_upload_on_creation(
    disabled_dsm_cleaner_task,
    aiopg_engine: Engine,
    simcore_s3_dsm: SimcoreS3DataManager,
    simcore_file_id: SimcoreS3FileID,
    simcore_directory_id: SimcoreS3FileID,
    user_id: UserID,
    file_size: ByteSize,
    is_directory: bool,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    checksum: SHA256Str | None,
):
    """This test reproduces what create_file_upload_links in dsm does, but running
    the cleaner in between to ensure the cleaner does not break the mechanism"""

    file_or_directory_id = simcore_directory_id if is_directory else simcore_file_id
    later_than_now = arrow.utcnow().datetime + datetime.timedelta(minutes=5)
    fmd = FileMetaData.from_simcore_node(
        user_id,
        file_or_directory_id,
        storage_s3_bucket,
        simcore_s3_dsm.location_id,
        simcore_s3_dsm.location_name,
        upload_expires_at=later_than_now,
        is_directory=is_directory,
        sha256_checksum=checksum,
    )
    # we create the entry in the db
    async with aiopg_engine.acquire() as conn:
        await db_file_meta_data.upsert(conn, fmd)

        # ensure the database is correctly set up
        fmd_in_db = await db_file_meta_data.get(conn, file_or_directory_id)
    assert fmd_in_db
    assert fmd_in_db.upload_expires_at
    # we create the multipart upload link

    # NOTE: generating more that 1 file since the previous implementation of the
    # _clean_dangling_multipart_uploads was working with 1 file in the directory,
    # adding multiple files broke it!
    FILES_IN_DIR: Final[int] = 5

    file_ids_to_upload: set[SimcoreS3FileID] = (
        {
            TypeAdapter(SimcoreS3FileID).validate_python(
                f"{file_or_directory_id}/file{x}"
            )
            for x in range(FILES_IN_DIR)
        }
        if is_directory
        else {simcore_file_id}
    )

    upload_links_list: list[MultiPartUploadLinks] = [
        await storage_s3_client.create_multipart_upload_links(
            bucket=storage_s3_bucket,
            object_key=file_id,
            file_size=file_size,
            expiration_secs=3600,
            sha256_checksum=TypeAdapter(SHA256Str).validate_python(_faker.sha256()),
        )
        for file_id in file_ids_to_upload
    ]
    started_multipart_uploads_upload_id: set[str] = {
        x.upload_id for x in upload_links_list
    }
    assert len(started_multipart_uploads_upload_id) == len(file_ids_to_upload)

    # ensure we have now an upload id
    all_ongoing_uploads: list[
        tuple[UploadID, SimcoreS3FileID]
    ] = await storage_s3_client.list_ongoing_multipart_uploads(bucket=storage_s3_bucket)
    assert len(all_ongoing_uploads) == len(file_ids_to_upload)

    for ongoing_upload_id, ongoing_file_id in all_ongoing_uploads:
        assert ongoing_upload_id in started_multipart_uploads_upload_id
        assert urllib.parse.unquote(ongoing_file_id) in file_ids_to_upload

    # now cleanup, we do not have an explicit upload_id in the database yet
    await simcore_s3_dsm.clean_expired_uploads()

    # ensure we STILL have the same upload id
    all_ongoing_uploads_after_clean = (
        await storage_s3_client.list_ongoing_multipart_uploads(bucket=storage_s3_bucket)
    )
    assert len(all_ongoing_uploads_after_clean) == len(file_ids_to_upload)
    assert all_ongoing_uploads == all_ongoing_uploads_after_clean
