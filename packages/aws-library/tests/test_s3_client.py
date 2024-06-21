# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


import filecmp
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Callable

import botocore.exceptions
import pytest
from aiohttp import ClientSession
from aws_library.s3.client import SimcoreS3API
from faker import Faker
from models_library.api_schemas_storage import S3BucketName
from moto.server import ThreadedMotoServer
from pydantic import AnyUrl, ByteSize, parse_obj_as
from pytest_simcore.helpers.utils_envs import EnvVarsDict
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
    await simcore_s3_api.create_bucket(bucket_name, region)
    assert await simcore_s3_api.bucket_exists(bucket_name)
    # calling again works and silently does nothing
    await simcore_s3_api.create_bucket(bucket_name, region)


@pytest.fixture
async def with_s3_bucket(
    s3_client: S3Client, bucket_name: S3BucketName
) -> AsyncIterator[S3BucketName]:
    await s3_client.create_bucket(Bucket=bucket_name)
    yield bucket_name
    await s3_client.delete_bucket(Bucket=bucket_name)


async def test_bucket_exists(
    simcore_s3_api: SimcoreS3API, with_s3_bucket: S3BucketName, faker: Faker
):
    invalid_bucket = parse_obj_as(S3BucketName, faker.pystr().replace("_", "-").lower())
    assert not await simcore_s3_api.bucket_exists(invalid_bucket)
    assert await simcore_s3_api.bucket_exists(with_s3_bucket)
    assert not await simcore_s3_api.http_check_bucket_connected(invalid_bucket)
    assert await simcore_s3_api.http_check_bucket_connected(with_s3_bucket)


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


@pytest.fixture
async def with_uploaded_file_on_s3(
    create_file_of_size: Callable[[ByteSize], Path],
    s3_client: S3Client,
    with_s3_bucket: S3BucketName,
) -> AsyncIterator[Path]:
    test_file = create_file_of_size(parse_obj_as(ByteSize, "10Kib"))
    await s3_client.upload_file(
        Filename=f"{test_file}", Bucket=with_s3_bucket, Key=test_file.name
    )

    yield test_file

    await s3_client.delete_object(Bucket=with_s3_bucket, Key=test_file.name)


async def test_create_single_presigned_download_link(
    mocked_s3_server_envs: EnvVarsDict,
    with_s3_bucket: S3BucketName,
    with_uploaded_file_on_s3: Path,
    simcore_s3_api: SimcoreS3API,
    tmp_path: Path,
    faker: Faker,
):
    download_url = await simcore_s3_api.create_single_presigned_download_link(
        bucket_name=with_s3_bucket,
        object_key=with_uploaded_file_on_s3.name,
        expiration_secs=50,
    )
    assert isinstance(download_url, AnyUrl)

    dest_file = tmp_path / faker.file_name()
    async with ClientSession() as session:
        response = await session.get(download_url)
        response.raise_for_status()
        with dest_file.open("wb") as fp:
            fp.write(await response.read())
    assert dest_file.exists()

    assert filecmp.cmp(dest_file, with_uploaded_file_on_s3) is True
