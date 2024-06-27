# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


import csv
import os
from collections.abc import AsyncIterator
from pathlib import Path

import botocore.exceptions
import pytest
from aws_library.s3.client import SimcoreS3API
from faker import Faker
from models_library.api_schemas_storage import S3BucketName
from moto.server import ThreadedMotoServer
from pydantic import AnyUrl
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from settings_library.s3 import S3Settings
from types_aiobotocore_s3 import S3Client


@pytest.fixture
async def simcore_s3_api(
    mocked_s3_server_settings: S3Settings,
) -> AsyncIterator[SimcoreS3API]:
    s3 = await SimcoreS3API.create(settings=mocked_s3_server_settings)
    assert s3
    assert s3.client
    assert s3.exit_stack
    assert s3.session
    yield s3
    await s3.close()


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
async def create_s3_bucket(
    mocked_s3_server_envs: EnvVarsDict, s3_client: S3Client, faker: Faker
) -> AsyncIterator[S3BucketName]:
    bucket_name = faker.pystr()
    await s3_client.create_bucket(Bucket=bucket_name)

    yield S3BucketName(bucket_name)

    await s3_client.delete_bucket(Bucket=bucket_name)


async def test_http_check_bucket_connected(
    mocked_aws_server: ThreadedMotoServer,
    simcore_s3_api: SimcoreS3API,
    create_s3_bucket: S3BucketName,
):
    assert (
        await simcore_s3_api.http_check_bucket_connected(bucket=create_s3_bucket)
        is True
    )
    mocked_aws_server.stop()
    assert (
        await simcore_s3_api.http_check_bucket_connected(bucket=create_s3_bucket)
        is False
    )
    mocked_aws_server.start()
    assert (
        await simcore_s3_api.http_check_bucket_connected(bucket=create_s3_bucket)
        is True
    )


@pytest.fixture
async def create_small_csv_file(tmp_path):
    data = [
        ["Name", "Age", "Country"],
        ["Alice", 25, "USA"],
        ["Bob", 30, "Canada"],
        ["Charlie", 22, "UK"],
    ]

    # Create a temporary file in the tmp_path directory
    csv_file_path = tmp_path / "small_csv_file.csv"

    # Write the data to the CSV file
    with open(csv_file_path, mode="w", newline="") as file:
        csv_writer = csv.writer(file)
        csv_writer.writerows(data)

    # Provide the CSV file path as the fixture value
    yield csv_file_path

    # Clean up: Remove the temporary CSV file after the test
    if csv_file_path.exists():
        os.remove(csv_file_path)


@pytest.fixture
async def upload_file_to_bucket(
    create_small_csv_file: Path,
    mocked_s3_server_envs: EnvVarsDict,
    s3_client: S3Client,
    create_s3_bucket: S3BucketName,
):
    await s3_client.upload_file(create_small_csv_file, create_s3_bucket, "test.csv")

    yield

    await s3_client.delete_object(Bucket=create_s3_bucket, Key="test.csv")


async def test_create_single_presigned_download_link(
    simcore_s3_api: SimcoreS3API, upload_file_to_bucket: None, create_s3_bucket
):
    download_url = await simcore_s3_api.create_single_presigned_download_link(
        create_s3_bucket, "test.csv", 50
    )
    assert isinstance(download_url, AnyUrl)
