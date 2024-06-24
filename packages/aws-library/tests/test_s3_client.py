# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


import asyncio
import filecmp
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import botocore.exceptions
import pytest
from aiohttp import ClientSession
from aws_library.s3.client import S3ObjectKey, SimcoreS3API
from aws_library.s3.constants import MULTIPART_UPLOADS_MIN_TOTAL_SIZE
from aws_library.s3.errors import (
    S3BucketInvalidError,
    S3KeyNotFoundError,
    S3UploadNotFoundError,
)
from aws_library.s3.models import MultiPartUploadLinks
from faker import Faker
from models_library.api_schemas_storage import S3BucketName, UploadedPart
from models_library.basic_types import SHA256Str
from moto.server import ThreadedMotoServer
from pydantic import AnyUrl, ByteSize, parse_obj_as
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from pytest_simcore.helpers.utils_parametrizations import (
    byte_size_ids,
    parametrized_file_size,
)
from pytest_simcore.helpers.utils_s3 import (
    delete_all_object_versions,
    upload_file_to_presigned_link,
)
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
    assert s3.client
    assert s3.exit_stack
    assert s3.session
    yield s3
    await s3.close()


@pytest.fixture
def bucket_name(faker: Faker) -> S3BucketName:
    # NOTE: no faker here as we need some specific namings
    return parse_obj_as(S3BucketName, faker.pystr().replace("_", "-").lower())


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
    return parse_obj_as(S3BucketName, faker.pystr().replace("_", "-").lower())


@pytest.fixture
async def upload_to_presigned_link(
    s3_client: S3Client,
) -> AsyncIterator[
    Callable[[Path, AnyUrl, S3BucketName, S3ObjectKey], Awaitable[None]]
]:
    uploaded_object_keys: list[tuple[S3BucketName, S3ObjectKey]] = []

    async def _(
        file: Path, presigned_url: AnyUrl, bucket: S3BucketName, s3_object: S3ObjectKey
    ) -> None:
        await upload_file_to_presigned_link(
            file,
            MultiPartUploadLinks(
                upload_id="fake",
                chunk_size=parse_obj_as(ByteSize, file.stat().st_size),
                urls=[presigned_url],
            ),
        )
        uploaded_object_keys.append((bucket, s3_object))

    yield _

    for bucket, object_key in uploaded_object_keys:
        await delete_all_object_versions(s3_client, bucket, object_key)


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
    test_file = create_file_of_size(parse_obj_as(ByteSize, "10Kib"))
    await s3_client.upload_file(
        Filename=f"{test_file}",
        Bucket=with_s3_bucket,
        Key=test_file.name,
    )

    yield UploadedFile(local_path=test_file, s3_key=test_file.name)

    await delete_all_object_versions(s3_client, with_s3_bucket, test_file.name)


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
            sha256_checksum=parse_obj_as(SHA256Str, faker.sha256()),
        )
        assert upload_links

        # check there is no file yet
        with pytest.raises(S3KeyNotFoundError, match=f"{object_key}"):
            await simcore_s3_api.get_file_metadata(
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
            await simcore_s3_api.get_file_metadata(
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

    for object_key in possibly_updated_files:
        await delete_all_object_versions(s3_client, with_s3_bucket, object_key)


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
        response = await simcore_s3_api.upload_file(
            bucket=with_s3_bucket,
            file=file,
            object_key=object_key,
            bytes_transfered_cb=None,
        )
        # there is no response from aioboto3...
        assert not response

        assert (
            await simcore_s3_api.file_exists(
                bucket=with_s3_bucket, object_key=object_key
            )
            is True
        )
        uploaded_object_keys.append(object_key)
        return UploadedFile(local_path=file, s3_key=object_key)

    yield _uploader

    await asyncio.gather(
        *[
            delete_all_object_versions(s3_client, with_s3_bucket, object_key)
            for object_key in uploaded_object_keys
        ]
    )


@pytest.fixture
async def with_uploaded_folder_on_s3(
    create_folder_of_size_with_multiple_files: Callable[[ByteSize, ByteSize], Path],
    upload_file: Callable[[Path, Path], Awaitable[UploadedFile]],
    directory_size: ByteSize,
    max_file_size: ByteSize,
) -> list[UploadedFile]:
    # create random files of random size and upload to S3
    folder = create_folder_of_size_with_multiple_files(
        ByteSize(directory_size), ByteSize(max_file_size)
    )
    print(f"uploading {folder}...")
    list_uploaded_files = await asyncio.gather(
        *[
            upload_file(file, folder.parent)
            for file in folder.rglob("*")
            if file.is_file()
        ]
    )
    print(f"uploaded {len(list_uploaded_files)} files")
    return list_uploaded_files


@pytest.fixture
async def copy_file(
    simcore_s3_api: SimcoreS3API, with_s3_bucket: S3BucketName, s3_client: S3Client
) -> AsyncIterator[Callable[[S3ObjectKey, S3ObjectKey], Awaitable[S3ObjectKey]]]:
    copied_object_keys = []

    async def _copier(src_key: S3ObjectKey, dst_key: S3ObjectKey) -> S3ObjectKey:
        await simcore_s3_api.copy_file(
            bucket=with_s3_bucket,
            src_object_key=src_key,
            dst_object_key=dst_key,
            bytes_transfered_cb=None,
        )
        copied_object_keys.append(dst_key)
        return dst_key

    yield _copier

    # cleanup
    for object_key in copied_object_keys:
        await delete_all_object_versions(s3_client, with_s3_bucket, object_key)


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
    s3_metadata = await simcore_s3_api.get_file_metadata(
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
        await simcore_s3_api.get_file_metadata(
            bucket=non_existing_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
        )


async def test_get_file_metadata_with_non_existing_key_raises(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    simcore_s3_api: SimcoreS3API,
    faker: Faker,
):
    with pytest.raises(S3KeyNotFoundError):
        await simcore_s3_api.get_file_metadata(
            bucket=with_s3_bucket, object_key=faker.pystr()
        )


async def test_delete_file(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    simcore_s3_api: SimcoreS3API,
    with_uploaded_file_on_s3: UploadedFile,
):
    # delete the file
    await simcore_s3_api.delete_file(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )

    # check it is not available
    assert not await simcore_s3_api.file_exists(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )

    # calling again does not raise
    await simcore_s3_api.delete_file(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )


async def test_delete_file_non_existing_bucket_raises(
    mocked_s3_server_envs: EnvVarsDict,
    non_existing_s3_bucket: S3BucketName,
    simcore_s3_api: SimcoreS3API,
    faker: Faker,
):
    with pytest.raises(S3BucketInvalidError):
        await simcore_s3_api.delete_file(
            bucket=non_existing_s3_bucket, object_key=faker.pystr()
        )


async def test_undelete_file(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    with_versioning_enabled: None,
    simcore_s3_api: SimcoreS3API,
    with_uploaded_file_on_s3: UploadedFile,
):
    # delete the file
    await simcore_s3_api.delete_file(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )

    # check it is not available
    assert (
        await simcore_s3_api.file_exists(
            bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
        )
        is False
    )

    # undelete the file
    await simcore_s3_api.undelete_file(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    # check the file is back
    await simcore_s3_api.file_exists(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )

    # delete the file again
    await simcore_s3_api.delete_file(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    # check it is not available
    assert (
        await simcore_s3_api.file_exists(
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
        await simcore_s3_api.undelete_file(
            bucket=non_existing_s3_bucket, object_key=faker.pystr()
        )
    with pytest.raises(S3KeyNotFoundError):
        await simcore_s3_api.undelete_file(
            bucket=with_s3_bucket, object_key=faker.pystr()
        )


async def test_undelete_file_with_no_versioning_raises(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    simcore_s3_api: SimcoreS3API,
    with_uploaded_file_on_s3: UploadedFile,
):
    await simcore_s3_api.delete_file(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    with pytest.raises(S3KeyNotFoundError):
        await simcore_s3_api.undelete_file(
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
    assert await simcore_s3_api.file_exists(
        bucket=with_s3_bucket, object_key=with_uploaded_file_on_s3.s3_key
    )
    download_url = await simcore_s3_api.create_single_presigned_download_link(
        bucket=with_s3_bucket,
        object_key=with_uploaded_file_on_s3.s3_key,
        expiration_secs=default_expiration_time_seconds,
    )
    assert isinstance(download_url, AnyUrl)

    dest_file = tmp_path / faker.file_name()
    async with ClientSession() as session:
        response = await session.get(download_url)
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
    file = create_file_of_size(parse_obj_as(ByteSize, "1Mib"))
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
    s3_metadata = await simcore_s3_api.get_file_metadata(
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
    file = create_file_of_size(parse_obj_as(ByteSize, "1Mib"))
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
    s3_metadata = await simcore_s3_api.get_file_metadata(
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
        parametrized_file_size(f"{MULTIPART_UPLOADS_MIN_TOTAL_SIZE}"),
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
            sha256_checksum=parse_obj_as(SHA256Str, faker.sha256()),
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
    s3_metadata = await simcore_s3_api.get_file_metadata(
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
        await simcore_s3_api.file_exists(bucket=with_s3_bucket, object_key=object_key)
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
        await simcore_s3_api.file_exists(
            bucket=with_s3_bucket, object_key=dst_object_key
        )
        is True
    )
    dst_file_metadata = await simcore_s3_api.get_file_metadata(
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
    file = create_file_of_size(parse_obj_as(ByteSize, "1MiB"))
    uploaded_file = await upload_file(file)
    dst_object_key = faker.file_name()
    with pytest.raises(S3BucketInvalidError, match=f"{non_existing_s3_bucket}"):
        await simcore_s3_api.copy_file(
            bucket=non_existing_s3_bucket,
            src_object_key=uploaded_file.s3_key,
            dst_object_key=dst_object_key,
            bytes_transfered_cb=None,
        )
    fake_src_key = faker.file_name()
    with pytest.raises(S3KeyNotFoundError, match=rf"{fake_src_key}"):
        await simcore_s3_api.copy_file(
            bucket=with_s3_bucket,
            src_object_key=fake_src_key,
            dst_object_key=dst_object_key,
            bytes_transfered_cb=None,
        )


@pytest.mark.parametrize(
    "directory_size, max_file_size",
    [(parse_obj_as(ByteSize, "1Mib"), parse_obj_as(ByteSize, "10Kib"))],
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
    "directory_size, max_file_size",
    [(parse_obj_as(ByteSize, "1Mib"), parse_obj_as(ByteSize, "10Kib"))],
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
    "directory_size, max_file_size",
    [(parse_obj_as(ByteSize, "1Mib"), parse_obj_as(ByteSize, "10Kib"))],
    ids=byte_size_ids,
)
async def test_delete_file_recursively(
    mocked_s3_server_envs: EnvVarsDict,
    simcore_s3_api: SimcoreS3API,
    with_s3_bucket: S3BucketName,
    with_uploaded_folder_on_s3: list[UploadedFile],
):
    # deleting from the root
    await simcore_s3_api.delete_file_recursively(
        bucket=with_s3_bucket,
        prefix=Path(with_uploaded_folder_on_s3[0].s3_key).parts[0],
    )
    files_exists = set(
        await asyncio.gather(
            *[
                simcore_s3_api.file_exists(
                    bucket=with_s3_bucket, object_key=file.s3_key
                )
                for file in with_uploaded_folder_on_s3
            ]
        )
    )
    assert len(files_exists) == 1
    assert next(iter(files_exists)) is False
