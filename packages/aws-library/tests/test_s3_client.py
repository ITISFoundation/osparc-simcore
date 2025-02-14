# pylint:disable=contextmanager-generator-missing-cleanup
# pylint:disable=no-name-in-module
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=unused-argument
# pylint:disable=unused-variable


import asyncio
import filecmp
import json
import logging
import random
import time
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import aiofiles
import botocore.exceptions
import pytest
from aiohttp import ClientSession
from aws_library.s3._client import S3ObjectKey, SimcoreS3API
from aws_library.s3._constants import (
    MULTIPART_COPY_THRESHOLD,
    MULTIPART_UPLOADS_MIN_TOTAL_SIZE,
)
from aws_library.s3._errors import (
    S3BucketInvalidError,
    S3DestinationNotEmptyError,
    S3KeyNotFoundError,
    S3UploadNotFoundError,
)
from aws_library.s3._models import MultiPartUploadLinks
from faker import Faker
from models_library.api_schemas_storage import S3BucketName, UploadedPart
from models_library.basic_types import SHA256Str
from moto.server import ThreadedMotoServer
from pydantic import AnyUrl, ByteSize, TypeAdapter
from pytest_benchmark.plugin import BenchmarkFixture
from pytest_mock import MockerFixture
from pytest_simcore.helpers.comparing import (
    assert_same_contents,
    assert_same_file_content,
    get_files_info_from_path,
)
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.parametrizations import (
    byte_size_ids,
    parametrized_file_size,
)
from pytest_simcore.helpers.s3 import (
    delete_all_object_versions,
    upload_file_to_presigned_link,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.archiving_utils import unarchive_dir
from servicelib.bytes_iters import ArchiveEntries, DiskStreamReader, get_zip_bytes_iter
from servicelib.bytes_iters._models import DataSize
from servicelib.file_utils import remove_directory
from servicelib.progress_bar import ProgressBarData
from servicelib.s3_utils import FileLikeBytesIterReader
from servicelib.utils import limited_as_completed, limited_gather
from settings_library.s3 import S3Settings
from types_aiobotocore_s3 import S3Client
from types_aiobotocore_s3.literals import BucketLocationConstraintType


@pytest.fixture
async def simcore_s3_api(
    mocked_s3_server_settings: S3Settings,
    mocked_s3_server_envs: EnvVarsDict,
) -> AsyncIterator[SimcoreS3API]:
    s3 = await SimcoreS3API.create(settings=mocked_s3_server_settings)
    assert s3
    assert s3._client  # noqa: SLF001
    assert s3._exit_stack  # noqa: SLF001
    assert s3._session  # noqa: SLF001
    yield s3
    await s3.close()


@pytest.fixture
def bucket_name(faker: Faker) -> S3BucketName:
    # NOTE: no faker here as we need some specific namings
    return TypeAdapter(S3BucketName).validate_python(
        faker.pystr().replace("_", "-").lower()
    )


@pytest.fixture
async def ensure_bucket_name_deleted(
    bucket_name: S3BucketName, s3_client: S3Client
) -> AsyncIterator[None]:
    yield
    await s3_client.delete_bucket(Bucket=bucket_name)


@pytest.fixture
async def with_s3_bucket(
    s3_client: S3Client, bucket_name: S3BucketName
) -> AsyncIterator[S3BucketName]:
    await s3_client.create_bucket(Bucket=bucket_name)
    yield bucket_name
    await s3_client.delete_bucket(Bucket=bucket_name)


@pytest.fixture
def non_existing_s3_bucket(faker: Faker) -> S3BucketName:
    return TypeAdapter(S3BucketName).validate_python(
        faker.pystr().replace("_", "-").lower()
    )


@pytest.fixture
async def upload_to_presigned_link(
    s3_client: S3Client,
) -> AsyncIterator[
    Callable[[Path, AnyUrl, S3BucketName, S3ObjectKey], Awaitable[None]]
]:
    uploaded_object_keys: dict[S3BucketName, list[S3ObjectKey]] = defaultdict(list)

    async def _(
        file: Path, presigned_url: AnyUrl, bucket: S3BucketName, s3_object: S3ObjectKey
    ) -> None:
        await upload_file_to_presigned_link(
            file,
            MultiPartUploadLinks(
                upload_id="fake",
                chunk_size=TypeAdapter(ByteSize).validate_python(file.stat().st_size),
                urls=[presigned_url],
            ),
        )
        uploaded_object_keys[bucket].append(s3_object)

    yield _

    for bucket, object_keys in uploaded_object_keys.items():
        await delete_all_object_versions(s3_client, bucket, object_keys)


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadedFile:
    local_path: Path
    s3_key: S3ObjectKey


@pytest.fixture
async def with_uploaded_file_on_s3(
    create_file_of_size: Callable[[ByteSize], Path],
    s3_client: S3Client,
    with_s3_bucket: S3BucketName,
) -> AsyncIterator[UploadedFile]:
    test_file = create_file_of_size(TypeAdapter(ByteSize).validate_python("10Kib"))
    await s3_client.upload_file(
        Filename=f"{test_file}",
        Bucket=with_s3_bucket,
        Key=test_file.name,
    )

    yield UploadedFile(local_path=test_file, s3_key=test_file.name)

    await delete_all_object_versions(s3_client, with_s3_bucket, [test_file.name])


@pytest.fixture
def default_expiration_time_seconds(faker: Faker) -> int:
    return faker.pyint(min_value=10)


@pytest.mark.parametrize("region", ["us-east-1", "us-east-2", "us-west-1", "us-west-2"])
async def test_create_bucket(
    simcore_s3_api: SimcoreS3API,
    bucket_name: S3BucketName,
    ensure_bucket_name_deleted: None,
    region: BucketLocationConstraintType,
):
    assert not await simcore_s3_api.bucket_exists(bucket=bucket_name)
    await simcore_s3_api.create_bucket(bucket=bucket_name, region=region)
    assert await simcore_s3_api.bucket_exists(bucket=bucket_name)
    # calling again works and silently does nothing
    await simcore_s3_api.create_bucket(bucket=bucket_name, region=region)


@pytest.fixture
async def with_versioning_enabled(
    s3_client: S3Client,
    with_s3_bucket: S3BucketName,
) -> None:
    await s3_client.put_bucket_versioning(
        Bucket=with_s3_bucket,
        VersioningConfiguration={"MFADelete": "Disabled", "Status": "Enabled"},
    )


@pytest.fixture
async def upload_file_to_multipart_presigned_link_without_completing(
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    create_file_of_size: Callable[[ByteSize], Path],
    faker: Faker,
    default_expiration_time_seconds: int,
    s3_client: S3Client,
) -> AsyncIterator[
    Callable[
        ..., Awaitable[tuple[S3ObjectKey, MultiPartUploadLinks, list[UploadedPart]]]
    ]
]:
    possibly_updated_files: list[S3ObjectKey] = []

    async def _uploader(
        file_size: ByteSize,
        object_key: S3ObjectKey | None = None,
    ) -> tuple[S3ObjectKey, MultiPartUploadLinks, list[UploadedPart]]:
        file = create_file_of_size(file_size)
        if not object_key:
            object_key = S3ObjectKey(file.name)
        upload_links = await simcore_s3_api.create_multipart_upload_links(
            bucket=with_s3_bucket,
            object_key=object_key,
            file_size=ByteSize(file.stat().st_size),
            expiration_secs=default_expiration_time_seconds,
            sha256_checksum=TypeAdapter(SHA256Str).validate_python(faker.sha256()),
        )
        assert upload_links

        # check there is no file yet
        with pytest.raises(S3KeyNotFoundError, match=f"{object_key}"):
            await simcore_s3_api.get_object_metadata(
                bucket=with_s3_bucket, object_key=object_key
            )

        # check we have the multipart upload initialized and listed
        ongoing_multipart_uploads = await simcore_s3_api.list_ongoing_multipart_uploads(
            bucket=with_s3_bucket
        )
        assert ongoing_multipart_uploads
        assert len(ongoing_multipart_uploads) == 1
        ongoing_upload_id, ongoing_object_key = ongoing_multipart_uploads[0]
        assert ongoing_upload_id == upload_links.upload_id
        assert ongoing_object_key == object_key

        # upload the file
        uploaded_parts: list[UploadedPart] = await upload_file_to_presigned_link(
            file,
            upload_links,
        )
        assert len(uploaded_parts) == len(upload_links.urls)

        # check there is no file yet
        with pytest.raises(S3KeyNotFoundError):
            await simcore_s3_api.get_object_metadata(
                bucket=with_s3_bucket, object_key=object_key
            )

        # check we have the multipart upload initialized and listed
        ongoing_multipart_uploads = await simcore_s3_api.list_ongoing_multipart_uploads(
            bucket=with_s3_bucket
        )
        assert ongoing_multipart_uploads
        assert len(ongoing_multipart_uploads) == 1
        ongoing_upload_id, ongoing_object_key = ongoing_multipart_uploads[0]
        assert ongoing_upload_id == upload_links.upload_id
        assert ongoing_object_key == object_key

        possibly_updated_files.append(object_key)

        return (
            object_key,
            upload_links,
            uploaded_parts,
        )

    yield _uploader

    await delete_all_object_versions(s3_client, with_s3_bucket, possibly_updated_files)


@dataclass
class _UploadProgressCallback:
    file_size: int
    action: str
    logger: logging.Logger
    _total_bytes_transfered: int = 0

    def __call__(self, bytes_transferred: int, *, file_name: str) -> None:
        self._total_bytes_transfered += bytes_transferred
        assert self._total_bytes_transfered <= self.file_size
        self.logger.info(
            "progress: %s",
            f"{self.action} {file_name=} {self._total_bytes_transfered} / {self.file_size} bytes",
        )


@dataclass
class _CopyProgressCallback:
    file_size: int
    action: str
    logger: logging.Logger
    _total_bytes_transfered: int = 0

    def __call__(self, total_bytes_copied: int, *, file_name: str) -> None:
        self._total_bytes_transfered = total_bytes_copied
        assert self._total_bytes_transfered <= self.file_size
        self.logger.info(
            "progress: %s",
            f"{self.action} {file_name=} {self._total_bytes_transfered} / {self.file_size} bytes",
        )


@pytest.fixture
async def upload_file(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    s3_client: S3Client,
) -> AsyncIterator[Callable[[Path], Awaitable[UploadedFile]]]:
    uploaded_object_keys = []

    async def _uploader(file: Path, base_path: Path | None = None) -> UploadedFile:
        object_key = file.name
        if base_path:
            object_key = f"{file.relative_to(base_path)}"
        with log_context(
            logging.INFO, msg=f"uploading {file} to {with_s3_bucket}/{object_key}"
        ) as ctx:
            progress_cb = _UploadProgressCallback(
                file_size=file.stat().st_size, action="uploaded", logger=ctx.logger
            )
            response = await simcore_s3_api.upload_file(
                bucket=with_s3_bucket,
                file=file,
                object_key=object_key,
                bytes_transfered_cb=progress_cb,
            )
        # there is no response from aioboto3...
        assert not response

        assert (
            await simcore_s3_api.object_exists(
                bucket=with_s3_bucket, object_key=object_key
            )
            is True
        )
        uploaded_object_keys.append(object_key)
        return UploadedFile(local_path=file, s3_key=object_key)

    yield _uploader

    with log_context(logging.INFO, msg=f"delete {len(uploaded_object_keys)}"):
        await delete_all_object_versions(
            s3_client, with_s3_bucket, uploaded_object_keys
        )


@pytest.fixture(autouse=True)
def set_log_levels_for_noisy_libraries() -> None:
    # Reduce the log level for 'werkzeug'
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


@pytest.fixture
async def with_uploaded_folder_on_s3(
    create_folder_of_size_with_multiple_files: Callable[
        [ByteSize, ByteSize, ByteSize, Path | None], Path
    ],
    upload_file: Callable[[Path, Path], Awaitable[UploadedFile]],
    directory_size: ByteSize,
    min_file_size: ByteSize,
    max_file_size: ByteSize,
) -> list[UploadedFile]:
    # create random files of random size and upload to S3
    folder = create_folder_of_size_with_multiple_files(
        ByteSize(directory_size), ByteSize(min_file_size), ByteSize(max_file_size), None
    )
    list_uploaded_files = []

    with log_context(logging.INFO, msg=f"uploading {folder}") as ctx:
        list_uploaded_files = [
            await uploaded_file
            async for uploaded_file in limited_as_completed(
                (
                    upload_file(file, folder.parent)
                    for file in folder.rglob("*")
                    if file.is_file()
                ),
                limit=20,
            )
        ]
        ctx.logger.info("uploaded %s files", len(list_uploaded_files))
    return list_uploaded_files


@pytest.fixture
async def copy_file(
    simcore_s3_api: SimcoreS3API, with_s3_bucket: S3BucketName, s3_client: S3Client
) -> AsyncIterator[Callable[[S3ObjectKey, S3ObjectKey], Awaitable[S3ObjectKey]]]:
    copied_object_keys = []

    async def _copier(src_key: S3ObjectKey, dst_key: S3ObjectKey) -> S3ObjectKey:
        file_metadata = await simcore_s3_api.get_object_metadata(
            bucket=with_s3_bucket, object_key=src_key
        )
        with log_context(logging.INFO, msg=f"copying {src_key} to {dst_key}") as ctx:
            progress_cb = _CopyProgressCallback(
                file_size=file_metadata.size, action="copied", logger=ctx.logger
            )
            await simcore_s3_api.copy_object(
                bucket=with_s3_bucket,
                src_object_key=src_key,
                dst_object_key=dst_key,
                bytes_transfered_cb=progress_cb,
            )
        copied_object_keys.append(dst_key)
        return dst_key

    yield _copier

    # cleanup
    await delete_all_object_versions(s3_client, with_s3_bucket, copied_object_keys)


@pytest.fixture
async def copy_files_recursively(
    simcore_s3_api: SimcoreS3API, with_s3_bucket: S3BucketName, s3_client: S3Client
) -> AsyncIterator[Callable[[str, str], Awaitable[str]]]:
    copied_dst_prefixes = []

    async def _copier(src_prefix: str, dst_prefix: str) -> str:
        src_directory_metadata = await simcore_s3_api.get_directory_metadata(
            bucket=with_s3_bucket, prefix=src_prefix
        )
        with log_context(
            logging.INFO,
            msg=f"copying {src_prefix} [{ByteSize(src_directory_metadata.size).human_readable()}] to {dst_prefix}",
        ) as ctx:
            progress_cb = _CopyProgressCallback(
                file_size=src_directory_metadata.size,
                action="copied",
                logger=ctx.logger,
            )
            await simcore_s3_api.copy_objects_recursively(
                bucket=with_s3_bucket,
                src_prefix=src_prefix,
                dst_prefix=dst_prefix,
                bytes_transfered_cb=progress_cb,
            )

        dst_directory_metadata = await simcore_s3_api.get_directory_metadata(
            bucket=with_s3_bucket, prefix=dst_prefix
        )
        assert dst_directory_metadata.size == src_directory_metadata.size

        copied_dst_prefixes.append(dst_prefix)
        return dst_prefix

    yield _copier

    # cleanup
    for dst_prefix in copied_dst_prefixes:
        await simcore_s3_api.delete_objects_recursively(
            bucket=with_s3_bucket, prefix=dst_prefix
        )


async def test_aiobotocore_s3_client_when_s3_server_goes_up_and_down(
    mocked_aws_server: ThreadedMotoServer,
    mocked_s3_server_envs: EnvVarsDict,
    s3_client: S3Client,
):
    # passes without exception
    await s3_client.list_buckets()
    mocked_aws_server.stop()
    with pytest.raises(botocore.exceptions.EndpointConnectionError):
        await s3_client.list_buckets()

    # restart
    mocked_aws_server.start()
    # passes without exception
    await s3_client.list_buckets()


async def test_bucket_exists(
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    non_existing_s3_bucket: S3BucketName,
):
    assert not await simcore_s3_api.bucket_exists(bucket=non_existing_s3_bucket)
    assert await simcore_s3_api.bucket_exists(bucket=with_s3_bucket)
    assert not await simcore_s3_api.http_check_bucket_connected(
        bucket=non_existing_s3_bucket
    )
    assert await simcore_s3_api.http_check_bucket_connected(bucket=with_s3_bucket)


async def test_http_check_bucket_connected(
    mocked_aws_server: ThreadedMotoServer,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
):
    assert (
        await simcore_s3_api.http_check_bucket_connected(bucket=with_s3_bucket) is True
    )
    mocked_aws_server.stop()
    assert (
        await simcore_s3_api.http_check_bucket_connected(bucket=with_s3_bucket) is False
    )
    mocked_aws_server.start()
    assert (
        await simcore_s3_api.http_check_bucket_connected(bucket=with_s3_bucket) is True
    )


async def test_get_file_metadata(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    with_uploaded_file_on_s3: UploadedFile,
    simcore_s3_api: SimcoreS3API,
    s3_client: S3Client,
):
    s3_metadata = await simcore_s3_api.get_object_metadata(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    aioboto_s3_object_response = await s3_client.get_object(
        Bucket=with_s3_bucket, Key=with_uploaded_file_on_s3.s3_key
    )
    assert s3_metadata.object_key == with_uploaded_file_on_s3.s3_key
    assert s3_metadata.last_modified == aioboto_s3_object_response["LastModified"]
    assert s3_metadata.e_tag == json.loads(aioboto_s3_object_response["ETag"])
    assert s3_metadata.sha256_checksum is None
    assert s3_metadata.size == aioboto_s3_object_response["ContentLength"]


async def test_get_file_metadata_with_non_existing_bucket_raises(
    mocked_s3_server_envs: EnvVarsDict,
    non_existing_s3_bucket: S3BucketName,
    with_uploaded_file_on_s3: UploadedFile,
    simcore_s3_api: SimcoreS3API,
):
    with pytest.raises(S3KeyNotFoundError):
        await simcore_s3_api.get_object_metadata(
            bucket=non_existing_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
        )


async def test_get_file_metadata_with_non_existing_key_raises(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    simcore_s3_api: SimcoreS3API,
    faker: Faker,
):
    with pytest.raises(S3KeyNotFoundError):
        await simcore_s3_api.get_object_metadata(
            bucket=with_s3_bucket, object_key=faker.pystr()
        )


async def test_delete_file(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    simcore_s3_api: SimcoreS3API,
    with_uploaded_file_on_s3: UploadedFile,
):
    # delete the file
    await simcore_s3_api.delete_object(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )

    # check it is not available
    assert not await simcore_s3_api.object_exists(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )

    # calling again does not raise
    await simcore_s3_api.delete_object(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )


async def test_delete_file_non_existing_bucket_raises(
    mocked_s3_server_envs: EnvVarsDict,
    non_existing_s3_bucket: S3BucketName,
    simcore_s3_api: SimcoreS3API,
    faker: Faker,
):
    with pytest.raises(S3BucketInvalidError):
        await simcore_s3_api.delete_object(
            bucket=non_existing_s3_bucket, object_key=faker.pystr()
        )


async def test_undelete_file(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    with_versioning_enabled: None,
    simcore_s3_api: SimcoreS3API,
    with_uploaded_file_on_s3: UploadedFile,
    upload_file: Callable[[Path, Path], Awaitable[UploadedFile]],
    create_file_of_size: Callable[[ByteSize], Path],
    s3_client: S3Client,
):
    # we have a file uploaded
    file_metadata = await simcore_s3_api.get_object_metadata(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    assert file_metadata.size == with_uploaded_file_on_s3.local_path.stat().st_size

    # upload another file on top of the existing one
    new_file = create_file_of_size(TypeAdapter(ByteSize).validate_python("5Kib"))
    await s3_client.upload_file(
        Filename=f"{new_file}",
        Bucket=with_s3_bucket,
        Key=file_metadata.object_key,
    )

    # check that the metadata changed
    new_file_metadata = await simcore_s3_api.get_object_metadata(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    assert new_file_metadata.size == new_file.stat().st_size
    assert file_metadata.e_tag != new_file_metadata.e_tag

    # this deletes the new_file, so it's gone
    await simcore_s3_api.delete_object(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    assert not await simcore_s3_api.object_exists(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )

    # undelete the file, the new file is back
    await simcore_s3_api.undelete_object(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    await simcore_s3_api.object_exists(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    assert (
        await simcore_s3_api.get_object_metadata(
            bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
        )
        == new_file_metadata
    )
    # does nothing
    await simcore_s3_api.undelete_object(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )

    # delete the file again
    await simcore_s3_api.delete_object(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    # check it is not available
    assert (
        await simcore_s3_api.object_exists(
            bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
        )
        is False
    )


async def test_undelete_file_raises_if_file_does_not_exists(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    non_existing_s3_bucket: S3BucketName,
    simcore_s3_api: SimcoreS3API,
    faker: Faker,
):
    with pytest.raises(S3BucketInvalidError):
        await simcore_s3_api.undelete_object(
            bucket=non_existing_s3_bucket, object_key=faker.pystr()
        )
    with pytest.raises(S3KeyNotFoundError):
        await simcore_s3_api.undelete_object(
            bucket=with_s3_bucket, object_key=faker.pystr()
        )


async def test_undelete_file_with_no_versioning_raises(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    simcore_s3_api: SimcoreS3API,
    with_uploaded_file_on_s3: UploadedFile,
):
    await simcore_s3_api.delete_object(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    with pytest.raises(S3KeyNotFoundError):
        await simcore_s3_api.undelete_object(
            bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
        )


async def test_create_single_presigned_download_link(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    with_uploaded_file_on_s3: UploadedFile,
    simcore_s3_api: SimcoreS3API,
    default_expiration_time_seconds: int,
    tmp_path: Path,
    faker: Faker,
):
    assert await simcore_s3_api.object_exists(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    download_url = await simcore_s3_api.create_single_presigned_download_link(
        bucket=with_s3_bucket,
        object_key=with_uploaded_file_on_s3.s3_key,
        expiration_secs=default_expiration_time_seconds,
    )
    assert download_url

    dest_file = tmp_path / faker.file_name()
    async with ClientSession() as session:
        response = await session.get(f"{download_url}")
        response.raise_for_status()
        with dest_file.open("wb") as fp:
            fp.write(await response.read())
    assert dest_file.exists()

    assert filecmp.cmp(dest_file, with_uploaded_file_on_s3.local_path) is True


async def test_create_single_presigned_download_link_of_invalid_object_key_raises(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    simcore_s3_api: SimcoreS3API,
    default_expiration_time_seconds: int,
    faker: Faker,
):
    with pytest.raises(S3KeyNotFoundError):
        await simcore_s3_api.create_single_presigned_download_link(
            bucket=with_s3_bucket,
            object_key=faker.file_name(),
            expiration_secs=default_expiration_time_seconds,
        )


async def test_create_single_presigned_download_link_of_invalid_bucket_raises(
    mocked_s3_server_envs: EnvVarsDict,
    non_existing_s3_bucket: S3BucketName,
    with_uploaded_file_on_s3: UploadedFile,
    simcore_s3_api: SimcoreS3API,
    default_expiration_time_seconds: int,
):
    with pytest.raises(S3BucketInvalidError):
        await simcore_s3_api.create_single_presigned_download_link(
            bucket=non_existing_s3_bucket,
            object_key=with_uploaded_file_on_s3.s3_key,
            expiration_secs=default_expiration_time_seconds,
        )


async def test_create_single_presigned_upload_link(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    simcore_s3_api: SimcoreS3API,
    create_file_of_size: Callable[[ByteSize], Path],
    default_expiration_time_seconds: int,
    upload_to_presigned_link: Callable[
        [Path, AnyUrl, S3BucketName, S3ObjectKey], Awaitable[None]
    ],
):
    file = create_file_of_size(TypeAdapter(ByteSize).validate_python("1Mib"))
    s3_object_key = file.name
    presigned_url = await simcore_s3_api.create_single_presigned_upload_link(
        bucket=with_s3_bucket,
        object_key=s3_object_key,
        expiration_secs=default_expiration_time_seconds,
    )
    assert presigned_url

    # upload the file with a fake multipart upload links structure
    await upload_to_presigned_link(file, presigned_url, with_s3_bucket, s3_object_key)

    # check it is there
    s3_metadata = await simcore_s3_api.get_object_metadata(
        bucket=with_s3_bucket, object_key=s3_object_key
    )
    assert s3_metadata.size == file.stat().st_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag


async def test_create_single_presigned_upload_link_with_non_existing_bucket_raises(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    non_existing_s3_bucket: S3BucketName,
    create_file_of_size: Callable[[ByteSize], Path],
    default_expiration_time_seconds: int,
):
    file = create_file_of_size(TypeAdapter(ByteSize).validate_python("1Mib"))
    s3_object_key = file.name
    with pytest.raises(S3BucketInvalidError):
        await simcore_s3_api.create_single_presigned_upload_link(
            bucket=non_existing_s3_bucket,
            object_key=s3_object_key,
            expiration_secs=default_expiration_time_seconds,
        )


@pytest.mark.parametrize(
    "file_size",
    [
        parametrized_file_size("10Mib"),
        parametrized_file_size("100Mib"),
        parametrized_file_size("1000Mib"),
    ],
    ids=byte_size_ids,
)
async def test_create_multipart_presigned_upload_link(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    upload_file_to_multipart_presigned_link_without_completing: Callable[
        ..., Awaitable[tuple[S3ObjectKey, MultiPartUploadLinks, list[UploadedPart]]]
    ],
    file_size: ByteSize,
):
    (
        file_id,
        upload_links,
        uploaded_parts,
    ) = await upload_file_to_multipart_presigned_link_without_completing(file_size)

    # now complete it
    received_e_tag = await simcore_s3_api.complete_multipart_upload(
        bucket=with_s3_bucket,
        object_key=file_id,
        upload_id=upload_links.upload_id,
        uploaded_parts=uploaded_parts,
    )

    # check that the multipart upload is not listed anymore
    list_ongoing_uploads = await simcore_s3_api.list_ongoing_multipart_uploads(
        bucket=with_s3_bucket
    )
    assert list_ongoing_uploads == []

    # check the object is complete
    s3_metadata = await simcore_s3_api.get_object_metadata(
        bucket=with_s3_bucket, object_key=file_id
    )
    assert s3_metadata.size == file_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag == f"{json.loads(received_e_tag)}"

    # completing again raises
    with pytest.raises(S3UploadNotFoundError):
        await simcore_s3_api.complete_multipart_upload(
            bucket=with_s3_bucket,
            object_key=file_id,
            upload_id=upload_links.upload_id,
            uploaded_parts=uploaded_parts,
        )


@pytest.mark.parametrize(
    "file_size",
    [
        parametrized_file_size(MULTIPART_UPLOADS_MIN_TOTAL_SIZE.human_readable()),
    ],
    ids=byte_size_ids,
)
async def test_create_multipart_presigned_upload_link_invalid_raises(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    non_existing_s3_bucket: S3BucketName,
    upload_file_to_multipart_presigned_link_without_completing: Callable[
        ..., Awaitable[tuple[S3ObjectKey, MultiPartUploadLinks, list[UploadedPart]]]
    ],
    file_size: ByteSize,
    create_file_of_size: Callable[[ByteSize], Path],
    faker: Faker,
    default_expiration_time_seconds: int,
):
    file = create_file_of_size(file_size)
    # creating links with invalid bucket
    with pytest.raises(S3BucketInvalidError):
        await simcore_s3_api.create_multipart_upload_links(
            bucket=non_existing_s3_bucket,
            object_key=faker.pystr(),
            file_size=ByteSize(file.stat().st_size),
            expiration_secs=default_expiration_time_seconds,
            sha256_checksum=TypeAdapter(SHA256Str).validate_python(faker.sha256()),
        )

    # completing with invalid bucket
    (
        object_key,
        upload_links,
        uploaded_parts,
    ) = await upload_file_to_multipart_presigned_link_without_completing(file_size)

    with pytest.raises(S3BucketInvalidError):
        await simcore_s3_api.complete_multipart_upload(
            bucket=non_existing_s3_bucket,
            object_key=object_key,
            upload_id=upload_links.upload_id,
            uploaded_parts=uploaded_parts,
        )

    # with pytest.raises(S3KeyNotFoundError):
    # NOTE: this does not raise... and it returns the file_id of the original file...
    await simcore_s3_api.complete_multipart_upload(
        bucket=with_s3_bucket,
        object_key=faker.pystr(),
        upload_id=upload_links.upload_id,
        uploaded_parts=uploaded_parts,
    )


@pytest.mark.parametrize("file_size", [parametrized_file_size("1Gib")])
async def test_break_completion_of_multipart_upload(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    upload_file_to_multipart_presigned_link_without_completing: Callable[
        ..., Awaitable[tuple[S3ObjectKey, MultiPartUploadLinks, list[UploadedPart]]]
    ],
    file_size: ByteSize,
):
    (
        object_key,
        upload_links,
        uploaded_parts,
    ) = await upload_file_to_multipart_presigned_link_without_completing(file_size)
    # let's break the completion very quickly task and see what happens
    VERY_SHORT_TIMEOUT = 0.2
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            simcore_s3_api.complete_multipart_upload(
                bucket=with_s3_bucket,
                object_key=object_key,
                upload_id=upload_links.upload_id,
                uploaded_parts=uploaded_parts,
            ),
            timeout=VERY_SHORT_TIMEOUT,
        )
    # check we have the multipart upload initialized and listed
    ongoing_multipart_uploads = await simcore_s3_api.list_ongoing_multipart_uploads(
        bucket=with_s3_bucket
    )
    assert ongoing_multipart_uploads
    assert len(ongoing_multipart_uploads) == 1
    ongoing_upload_id, ongoing_file_id = ongoing_multipart_uploads[0]
    assert ongoing_upload_id == upload_links.upload_id
    assert ongoing_file_id == object_key

    # now wait
    await asyncio.sleep(10)

    # check that the completion of the update completed...
    assert (
        await simcore_s3_api.list_ongoing_multipart_uploads(bucket=with_s3_bucket) == []
    )

    # check the object is complete
    s3_metadata = await simcore_s3_api.get_object_metadata(
        bucket=with_s3_bucket, object_key=object_key
    )
    assert s3_metadata.size == file_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag


@pytest.mark.parametrize(
    "file_size",
    [parametrized_file_size(f"{MULTIPART_UPLOADS_MIN_TOTAL_SIZE}")],
    ids=byte_size_ids,
)
async def test_abort_multipart_upload(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    non_existing_s3_bucket: S3BucketName,
    upload_file_to_multipart_presigned_link_without_completing: Callable[
        ..., Awaitable[tuple[S3ObjectKey, MultiPartUploadLinks, list[UploadedPart]]]
    ],
    file_size: ByteSize,
    faker: Faker,
):
    (
        object_key,
        upload_links,
        _,
    ) = await upload_file_to_multipart_presigned_link_without_completing(file_size)

    # first abort with wrong bucket shall raise
    with pytest.raises(S3BucketInvalidError):
        await simcore_s3_api.abort_multipart_upload(
            bucket=non_existing_s3_bucket,
            object_key=object_key,
            upload_id=upload_links.upload_id,
        )

    # now abort it
    await simcore_s3_api.abort_multipart_upload(
        bucket=with_s3_bucket,
        object_key=faker.pystr(),
        upload_id=upload_links.upload_id,
    )
    # doing it again raises
    with pytest.raises(S3UploadNotFoundError):
        await simcore_s3_api.abort_multipart_upload(
            bucket=with_s3_bucket,
            object_key=object_key,
            upload_id=upload_links.upload_id,
        )

    # now check that the listing is empty
    ongoing_multipart_uploads = await simcore_s3_api.list_ongoing_multipart_uploads(
        bucket=with_s3_bucket
    )
    assert ongoing_multipart_uploads == []

    # check it is not available
    assert (
        await simcore_s3_api.object_exists(bucket=with_s3_bucket, object_key=object_key)
        is False
    )


@pytest.mark.parametrize(
    "file_size",
    [parametrized_file_size("500Mib")],
    ids=byte_size_ids,
)
async def test_upload_file(
    mocked_s3_server_envs: EnvVarsDict,
    upload_file: Callable[[Path], Awaitable[UploadedFile]],
    file_size: ByteSize,
    create_file_of_size: Callable[[ByteSize], Path],
):
    file = create_file_of_size(file_size)
    await upload_file(file)


async def test_upload_file_invalid_raises(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    non_existing_s3_bucket: S3BucketName,
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    faker: Faker,
):
    file = create_file_of_size(ByteSize(10), None)
    with pytest.raises(S3BucketInvalidError):
        await simcore_s3_api.upload_file(
            bucket=non_existing_s3_bucket,
            file=file,
            object_key=faker.pystr(),
            bytes_transfered_cb=None,
        )


@pytest.mark.parametrize(
    "file_size",
    [parametrized_file_size("500Mib")],
    ids=byte_size_ids,
)
async def test_copy_file(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    file_size: ByteSize,
    upload_file: Callable[[Path], Awaitable[UploadedFile]],
    copy_file: Callable[[S3ObjectKey, S3ObjectKey], Awaitable[S3ObjectKey]],
    create_file_of_size: Callable[[ByteSize], Path],
    faker: Faker,
):
    file = create_file_of_size(file_size)
    uploaded_file = await upload_file(file)
    dst_object_key = faker.file_name()
    await copy_file(uploaded_file.s3_key, dst_object_key)

    # check the object is uploaded
    assert (
        await simcore_s3_api.object_exists(
            bucket=with_s3_bucket, object_key=dst_object_key
        )
        is True
    )
    dst_file_metadata = await simcore_s3_api.get_object_metadata(
        bucket=with_s3_bucket, object_key=dst_object_key
    )
    assert uploaded_file.local_path.stat().st_size == dst_file_metadata.size


async def test_copy_file_invalid_raises(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    non_existing_s3_bucket: S3BucketName,
    upload_file: Callable[[Path], Awaitable[UploadedFile]],
    create_file_of_size: Callable[[ByteSize], Path],
    faker: Faker,
):
    file = create_file_of_size(TypeAdapter(ByteSize).validate_python("1MiB"))
    uploaded_file = await upload_file(file)
    dst_object_key = faker.file_name()
    # NOTE: since aioboto3 13.1.0 this raises S3KeyNotFoundError instead of S3BucketInvalidError
    with pytest.raises(S3KeyNotFoundError, match=f"{non_existing_s3_bucket}"):
        await simcore_s3_api.copy_object(
            bucket=non_existing_s3_bucket,
            src_object_key=uploaded_file.s3_key,
            dst_object_key=dst_object_key,
            bytes_transfered_cb=None,
        )
    fake_src_key = faker.file_name()
    with pytest.raises(S3KeyNotFoundError, match=rf"{fake_src_key}"):
        await simcore_s3_api.copy_object(
            bucket=with_s3_bucket,
            src_object_key=fake_src_key,
            dst_object_key=dst_object_key,
            bytes_transfered_cb=None,
        )


@pytest.mark.parametrize(
    "directory_size, min_file_size, max_file_size",
    [
        (
            TypeAdapter(ByteSize).validate_python("1Mib"),
            TypeAdapter(ByteSize).validate_python("1B"),
            TypeAdapter(ByteSize).validate_python("10Kib"),
        )
    ],
    ids=byte_size_ids,
)
async def test_get_directory_metadata(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    with_uploaded_folder_on_s3: list[UploadedFile],
    directory_size: ByteSize,
):
    metadata = await simcore_s3_api.get_directory_metadata(
        bucket=with_s3_bucket,
        prefix=Path(with_uploaded_folder_on_s3[0].s3_key).parts[0],
    )
    assert metadata
    assert metadata.size == directory_size


@pytest.mark.parametrize(
    "directory_size, min_file_size, max_file_size",
    [
        (
            TypeAdapter(ByteSize).validate_python("1Mib"),
            TypeAdapter(ByteSize).validate_python("1B"),
            TypeAdapter(ByteSize).validate_python("10Kib"),
        )
    ],
    ids=byte_size_ids,
)
async def test_get_directory_metadata_raises(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    non_existing_s3_bucket: S3BucketName,
    with_uploaded_folder_on_s3: list[UploadedFile],
):
    with pytest.raises(S3BucketInvalidError, match=rf"{non_existing_s3_bucket}"):
        await simcore_s3_api.get_directory_metadata(
            bucket=non_existing_s3_bucket,
            prefix=Path(with_uploaded_folder_on_s3[0].s3_key).parts[0],
        )

    wrong_prefix = "/"
    metadata = await simcore_s3_api.get_directory_metadata(
        bucket=with_s3_bucket,
        prefix=wrong_prefix,
    )
    assert metadata.size == 0


@pytest.mark.parametrize(
    "directory_size, min_file_size, max_file_size",
    [
        (
            TypeAdapter(ByteSize).validate_python("1Mib"),
            TypeAdapter(ByteSize).validate_python("1B"),
            TypeAdapter(ByteSize).validate_python("10Kib"),
        )
    ],
    ids=byte_size_ids,
)
async def test_delete_file_recursively(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    with_uploaded_folder_on_s3: list[UploadedFile],
):
    # deleting from the root
    await simcore_s3_api.delete_objects_recursively(
        bucket=with_s3_bucket,
        prefix=Path(with_uploaded_folder_on_s3[0].s3_key).parts[0],
    )
    files_exists = set(
        await asyncio.gather(
            *[
                simcore_s3_api.object_exists(
                    bucket=with_s3_bucket, object_key=file.s3_key
                )
                for file in with_uploaded_folder_on_s3
            ]
        )
    )
    assert len(files_exists) == 1
    assert next(iter(files_exists)) is False


@pytest.mark.parametrize(
    "directory_size, min_file_size, max_file_size",
    [
        (
            TypeAdapter(ByteSize).validate_python("1Mib"),
            TypeAdapter(ByteSize).validate_python("1B"),
            TypeAdapter(ByteSize).validate_python("10Kib"),
        )
    ],
    ids=byte_size_ids,
)
async def test_delete_file_recursively_raises(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    non_existing_s3_bucket: S3BucketName,
    with_s3_bucket: S3BucketName,
    with_uploaded_folder_on_s3: list[UploadedFile],
    faker: Faker,
):
    with pytest.raises(S3BucketInvalidError, match=rf"{non_existing_s3_bucket}"):
        await simcore_s3_api.delete_objects_recursively(
            bucket=non_existing_s3_bucket,
            prefix=Path(with_uploaded_folder_on_s3[0].s3_key).parts[0],
        )
    # this will do nothing
    await simcore_s3_api.delete_objects_recursively(
        bucket=with_s3_bucket,
        prefix=f"{faker.pystr()}",
    )
    # and this files still exist
    some_file = next(
        iter(filter(lambda f: f.local_path.is_file(), with_uploaded_folder_on_s3))
    )
    await simcore_s3_api.object_exists(
        bucket=with_s3_bucket, object_key=some_file.s3_key
    )


@pytest.mark.parametrize(
    "directory_size, min_file_size, max_file_size",
    [
        (
            TypeAdapter(ByteSize).validate_python("1Mib"),
            TypeAdapter(ByteSize).validate_python("1B"),
            TypeAdapter(ByteSize).validate_python("10Kib"),
        )
    ],
    ids=byte_size_ids,
)
async def test_copy_files_recursively(
    mocked_s3_server_envs: EnvVarsDict,
    with_uploaded_folder_on_s3: list[UploadedFile],
    copy_files_recursively: Callable[[str, str], Awaitable[str]],
):
    src_folder = Path(with_uploaded_folder_on_s3[0].s3_key).parts[0]
    dst_folder = f"{src_folder}-copy"
    await copy_files_recursively(src_folder, dst_folder)

    # doing it again shall raise
    with pytest.raises(S3DestinationNotEmptyError, match=rf"{dst_folder}"):
        await copy_files_recursively(src_folder, dst_folder)


async def test_copy_files_recursively_raises(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    non_existing_s3_bucket: S3BucketName,
):
    with pytest.raises(S3BucketInvalidError, match=rf"{non_existing_s3_bucket}"):
        await simcore_s3_api.copy_objects_recursively(
            bucket=non_existing_s3_bucket,
            src_prefix="",
            dst_prefix="",
            bytes_transfered_cb=None,
        )


@pytest.mark.parametrize(
    "file_size, expected_multipart",
    [
        (MULTIPART_UPLOADS_MIN_TOTAL_SIZE - 1, False),
        (MULTIPART_UPLOADS_MIN_TOTAL_SIZE, True),
    ],
)
def test_is_multipart(file_size: ByteSize, expected_multipart: bool):
    assert SimcoreS3API.is_multipart(file_size) == expected_multipart


@pytest.mark.parametrize(
    "bucket, object_key, expected_s3_url",
    [
        (
            "some-bucket",
            "an/object/separate/by/slashes",
            TypeAdapter(AnyUrl).validate_python(
                "s3://some-bucket/an/object/separate/by/slashes"
            ),
        ),
        (
            "some-bucket",
            "an/object/separate/by/slashes-?/3#$",
            TypeAdapter(AnyUrl).validate_python(
                r"s3://some-bucket/an/object/separate/by/slashes-%3F/3%23%24"
            ),
        ),
    ],
)
def test_compute_s3_url(
    bucket: S3BucketName, object_key: S3ObjectKey, expected_s3_url: AnyUrl
):
    assert (
        SimcoreS3API.compute_s3_url(bucket=bucket, object_key=object_key)
        == expected_s3_url
    )


@pytest.mark.parametrize(
    "file_size",
    [
        parametrized_file_size("10Mib"),
        parametrized_file_size("100Mib"),
        parametrized_file_size("1000Mib"),
    ],
    ids=byte_size_ids,
)
def test_upload_file_performance(
    mocked_s3_server_envs: EnvVarsDict,
    create_file_of_size: Callable[[ByteSize], Path],
    file_size: ByteSize,
    upload_file: Callable[[Path, Path | None], Awaitable[UploadedFile]],
    benchmark: BenchmarkFixture,
):

    # create random files of random size and upload to S3
    file = create_file_of_size(file_size)

    def run_async_test(*args, **kwargs) -> None:
        asyncio.get_event_loop().run_until_complete(upload_file(file, None))

    benchmark(run_async_test)


@pytest.mark.parametrize(
    "directory_size, min_file_size, max_file_size",
    [
        (
            TypeAdapter(ByteSize).validate_python("1Mib"),
            TypeAdapter(ByteSize).validate_python("1B"),
            TypeAdapter(ByteSize).validate_python("10Kib"),
        ),
        (
            TypeAdapter(ByteSize).validate_python("500Mib"),
            TypeAdapter(ByteSize).validate_python("10Mib"),
            TypeAdapter(ByteSize).validate_python("50Mib"),
        ),
    ],
    ids=byte_size_ids,
)
def test_copy_recurively_performance(
    mocked_s3_server_envs: EnvVarsDict,
    with_uploaded_folder_on_s3: list[UploadedFile],
    copy_files_recursively: Callable[[str, str], Awaitable[str]],
    benchmark: BenchmarkFixture,
):
    src_folder = Path(with_uploaded_folder_on_s3[0].s3_key).parts[0]

    folder_index = 0

    def dst_folder_setup() -> tuple[tuple[str], dict[str, Any]]:
        nonlocal folder_index
        dst_folder = f"{src_folder}-copy-{folder_index}"
        folder_index += 1
        return (dst_folder,), {}

    def run_async_test(dst_folder: str) -> None:
        asyncio.get_event_loop().run_until_complete(
            copy_files_recursively(src_folder, dst_folder)
        )

    benchmark.pedantic(run_async_test, setup=dst_folder_setup, rounds=4)


async def test_read_object_file_stream(
    mocked_s3_server_envs: EnvVarsDict,
    with_uploaded_file_on_s3: UploadedFile,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    fake_file_name: Path,
):
    async with aiofiles.open(fake_file_name, "wb") as f:
        bytes_streamer = await simcore_s3_api.get_bytes_streamer_from_object(
            with_s3_bucket, with_uploaded_file_on_s3.s3_key, chunk_size=1024
        )
        assert isinstance(bytes_streamer.data_size, DataSize)
        async for chunk in bytes_streamer.with_progress_bytes_iter(AsyncMock()):
            await f.write(chunk)

    assert bytes_streamer.data_size == fake_file_name.stat().st_size

    await assert_same_file_content(with_uploaded_file_on_s3.local_path, fake_file_name)


async def test_upload_object_from_file_like(
    mocked_s3_server_envs: EnvVarsDict,
    with_uploaded_file_on_s3: UploadedFile,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
):
    object_key = "read_from_s3_write_to_s3"
    bytes_streamer = await simcore_s3_api.get_bytes_streamer_from_object(
        with_s3_bucket, with_uploaded_file_on_s3.s3_key
    )
    assert isinstance(bytes_streamer.data_size, DataSize)

    await simcore_s3_api.upload_object_from_file_like(
        with_s3_bucket,
        object_key,
        FileLikeBytesIterReader(bytes_streamer.with_progress_bytes_iter(AsyncMock())),
    )

    # TODO: also add a test uploading form a file instead of S3 since it's possible, open it with aiofiles

    await simcore_s3_api.delete_object(bucket=with_s3_bucket, object_key=object_key)


@contextmanager
def _folder_with_files(
    create_folder_of_size_with_multiple_files: Callable[
        [ByteSize, ByteSize, ByteSize, Path | None], Path
    ],
    target_folder: Path,
) -> Iterator[dict[str, Path]]:
    target_folder.mkdir(parents=True, exist_ok=True)
    folder_path = create_folder_of_size_with_multiple_files(
        TypeAdapter(ByteSize).validate_python("10MiB"),
        TypeAdapter(ByteSize).validate_python("10KiB"),
        TypeAdapter(ByteSize).validate_python("100KiB"),
        target_folder,
    )

    relative_names_to_paths = get_files_info_from_path(folder_path)

    yield relative_names_to_paths

    for file in relative_names_to_paths.values():
        file.unlink()


@pytest.fixture
def path_local_files_for_archive(
    tmp_path: Path,
    create_folder_of_size_with_multiple_files: Callable[
        [ByteSize, ByteSize, ByteSize, Path | None], Path
    ],
) -> Iterator[Path]:
    dir_path = tmp_path / "not_uploaded"
    with _folder_with_files(create_folder_of_size_with_multiple_files, dir_path):
        yield dir_path


@pytest.fixture
async def path_s3_files_for_archive(
    tmp_path: Path,
    create_folder_of_size_with_multiple_files: Callable[
        [ByteSize, ByteSize, ByteSize, Path | None], Path
    ],
    s3_client: S3Client,
    with_s3_bucket: S3BucketName,
) -> AsyncIterator[Path]:
    dir_path = tmp_path / "stored_in_s3"
    with _folder_with_files(
        create_folder_of_size_with_multiple_files, dir_path
    ) as relative_names_to_paths:
        await limited_gather(
            *(
                s3_client.upload_file(
                    Filename=f"{file}", Bucket=with_s3_bucket, Key=s3_object_key
                )
                for s3_object_key, file in relative_names_to_paths.items()
            ),
            limit=10,
        )
        yield dir_path

        await delete_all_object_versions(
            s3_client, with_s3_bucket, relative_names_to_paths.keys()
        )


@pytest.fixture
def archive_download_path(tmp_path: Path, faker: Faker) -> Iterator[Path]:
    path = tmp_path / f"downlaoded_ardhive_{faker.uuid4()}.zip"
    yield path
    if path.exists():
        path.unlink()


@pytest.fixture
async def extracted_archive_path(tmp_path: Path, faker: Faker) -> AsyncIterator[Path]:
    path = tmp_path / f"decomrepssed_archive{faker.uuid4()}"
    path.mkdir(parents=True, exist_ok=True)
    assert path.is_dir()
    yield path
    await remove_directory(path)
    assert not path.is_dir()


@pytest.fixture
async def archive_s3_object_key(
    with_s3_bucket: S3BucketName, simcore_s3_api: SimcoreS3API
) -> AsyncIterator[S3ObjectKey]:
    s3_object_key = "read_from_s3_write_to_s3"
    yield s3_object_key
    await simcore_s3_api.delete_object(bucket=with_s3_bucket, object_key=s3_object_key)


@pytest.fixture
def mocked_progress_bar_cb(mocker: MockerFixture) -> Mock:
    def _progress_cb(*args, **kwargs) -> None:
        print(f"received progress: {args}, {kwargs}")

    return mocker.Mock(side_effect=_progress_cb)


async def test_workflow_compress_s3_objects_and_local_files_in_a_single_archive_then_upload_to_s3(
    mocked_s3_server_envs: EnvVarsDict,
    path_local_files_for_archive: Path,
    path_s3_files_for_archive: Path,
    archive_download_path: Path,
    extracted_archive_path: Path,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    s3_client: S3Client,
    archive_s3_object_key: S3ObjectKey,
    mocked_progress_bar_cb: Mock,
):
    # In this test:
    # - files are read form disk and S3
    # - a zip archive is created on the go
    # - the zip archive is streamed to S3 as soon as chunks inside it are created
    # Uses no disk and constant memory for the entire opration.

    # 1. assemble and upload zip archive

    archive_entries: ArchiveEntries = []

    local_files = get_files_info_from_path(path_local_files_for_archive)
    for file_name, file_path in local_files.items():
        archive_entries.append(
            (
                file_name,
                DiskStreamReader(file_path).get_bytes_streamer(),
            )
        )

    s3_files = get_files_info_from_path(path_s3_files_for_archive)

    for s3_object_key in s3_files:
        archive_entries.append(
            (
                s3_object_key,
                await simcore_s3_api.get_bytes_streamer_from_object(
                    with_s3_bucket, s3_object_key
                ),
            )
        )

    # shuffle order of files in archive.
    # some will be read from S3 and some from the disk
    random.shuffle(archive_entries)

    started = time.time()

    async with ProgressBarData(
        num_steps=1,
        progress_report_cb=mocked_progress_bar_cb,
        description="root_bar",
    ) as progress_bar:
        await simcore_s3_api.upload_object_from_file_like(
            with_s3_bucket,
            archive_s3_object_key,
            FileLikeBytesIterReader(
                get_zip_bytes_iter(
                    archive_entries,
                    progress_bar=progress_bar,
                    chunk_size=MULTIPART_COPY_THRESHOLD,
                )
            ),
        )

    duration = time.time() - started
    print(f"Zip created on S3 in {duration:.2f} seconds")

    # 2. download zip archive form S3
    print(f"downloading {archive_download_path}")
    await s3_client.download_file(
        with_s3_bucket, archive_s3_object_key, f"{archive_download_path}"
    )

    # 3. extract archive
    await unarchive_dir(archive_download_path, extracted_archive_path)

    # 4. compare
    print("comparing files")
    all_files_in_zip = get_files_info_from_path(path_local_files_for_archive) | s3_files

    await assert_same_contents(
        all_files_in_zip, get_files_info_from_path(extracted_archive_path)
    )
