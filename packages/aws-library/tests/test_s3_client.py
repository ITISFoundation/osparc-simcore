# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


import filecmp
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable

import botocore.exceptions
import pytest
from aiohttp import ClientSession
from aws_library.s3.client import S3ObjectKey, SimcoreS3API
from aws_library.s3.errors import S3BucketInvalidError, S3KeyNotFoundError
from aws_library.s3.models import MultiPartUploadLinks
from faker import Faker
from models_library.api_schemas_storage import S3BucketName
from moto.server import ThreadedMotoServer
from pydantic import AnyUrl, ByteSize, parse_obj_as
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from pytest_simcore.helpers.utils_s3 import upload_file_to_presigned_link
from settings_library.s3 import S3Settings
from types_aiobotocore_s3 import S3Client
from types_aiobotocore_s3.literals import BucketLocationConstraintType


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
async def with_s3_bucket(
    s3_client: S3Client, bucket_name: S3BucketName
) -> AsyncIterator[S3BucketName]:
    await s3_client.create_bucket(Bucket=bucket_name)
    yield bucket_name
    await s3_client.delete_bucket(Bucket=bucket_name)


@pytest.fixture
def non_existing_s3_bucket(faker: Faker) -> S3BucketName:
    return parse_obj_as(S3BucketName, faker.pystr().replace("_", "-").lower())


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

    await s3_client.delete_object(Bucket=with_s3_bucket, Key=test_file.name)


@pytest.fixture
def default_expiration_time_seconds(faker: Faker) -> int:
    return faker.pyint(min_value=10)


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
        await s3_client.delete_object(Bucket=bucket, Key=object_key)


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
