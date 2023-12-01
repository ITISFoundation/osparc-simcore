import contextlib
import typing

import aioboto3
import pytest
from aiobotocore.session import ClientCreatorContext
from botocore.client import Config
from faker import Faker
from settings_library.s3 import S3Settings
from types_aiobotocore_s3 import S3Client


@pytest.fixture
async def s3_client(
    mocked_s3_server_settings: S3Settings,
) -> typing.AsyncIterator[S3Client]:
    session = aioboto3.Session()
    exit_stack = contextlib.AsyncExitStack()
    session_client = session.client(
        "s3",
        endpoint_url=mocked_s3_server_settings.S3_ENDPOINT,
        aws_access_key_id=mocked_s3_server_settings.S3_ACCESS_KEY,
        aws_secret_access_key=mocked_s3_server_settings.S3_SECRET_KEY,
        aws_session_token=mocked_s3_server_settings.S3_ACCESS_TOKEN,
        region_name=mocked_s3_server_settings.S3_REGION,
        config=Config(signature_version="s3v4"),
    )
    assert isinstance(session_client, ClientCreatorContext)
    client = typing.cast(S3Client, await exit_stack.enter_async_context(session_client))

    yield client

    await exit_stack.aclose()


@pytest.fixture
async def s3_bucket(s3_client: S3Client, faker: Faker) -> str:
    response = await s3_client.list_buckets()
    assert not response["Buckets"]
    bucket_name = faker.pystr()
    await s3_client.create_bucket(Bucket=bucket)
    response = await s3_client.list_buckets()
    assert response["Buckets"]
    assert bucket_name in [
        bucket_struct.get("Name") for bucket_struct in response["Buckets"]
    ], f"failed creating {bucket_name}"

    return bucket_name
