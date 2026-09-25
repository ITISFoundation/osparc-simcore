# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import


import contextlib
import typing

import aioboto3
import pytest
from aiobotocore.session import ClientCreatorContext
from botocore.client import Config
from settings_library.s3 import S3Settings
from types_aiobotocore_s3 import S3Client

from .helpers.xdist import get_worker_id


@pytest.fixture
def s3_settings(request: pytest.FixtureRequest) -> S3Settings:
    settings = S3Settings.create_from_envs()

    # under xdist, each worker gets its own bucket on the SAME shared S3/rustfs container, so
    # concurrent workers never race create/empty on the same bucket name
    worker_id = get_worker_id(request)
    if worker_id != "master":
        settings = settings.model_copy(update={"S3_BUCKET_NAME": f"{settings.S3_BUCKET_NAME}_{worker_id}"})

    return settings


@pytest.fixture
async def s3_client(s3_settings: S3Settings) -> typing.AsyncIterator[S3Client]:
    session = aioboto3.Session()
    exit_stack = contextlib.AsyncExitStack()
    session_client = session.client(
        "s3",
        endpoint_url=f"{s3_settings.S3_ENDPOINT}" if s3_settings.S3_ENDPOINT else None,
        aws_access_key_id=s3_settings.S3_ACCESS_KEY.get_secret_value(),
        aws_secret_access_key=s3_settings.S3_SECRET_KEY.get_secret_value(),
        region_name=s3_settings.S3_REGION,
        config=Config(signature_version="s3v4"),
    )
    assert isinstance(session_client, ClientCreatorContext)
    client = typing.cast(S3Client, await exit_stack.enter_async_context(session_client))  # type: ignore[arg-type]

    yield client

    await exit_stack.aclose()


async def _empty_bucket(s3_client: S3Client, bucket_name: str) -> None:
    # List object versions
    response = await s3_client.list_object_versions(Bucket=bucket_name)

    # Delete all object versions
    for version in response.get("Versions", []):
        assert "Key" in version
        assert "VersionId" in version
        await s3_client.delete_object(Bucket=bucket_name, Key=version["Key"], VersionId=version["VersionId"])

    # Delete all delete markers
    for marker in response.get("DeleteMarkers", []):
        assert "Key" in marker
        assert "VersionId" in marker
        await s3_client.delete_object(Bucket=bucket_name, Key=marker["Key"], VersionId=marker["VersionId"])

    # Delete remaining objects in the bucket
    response = await s3_client.list_objects(Bucket=bucket_name)
    for obj in response.get("Contents", []):
        assert "Key" in obj
        await s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])


@pytest.fixture
async def s3_bucket(s3_settings: S3Settings, s3_client: S3Client) -> typing.AsyncIterator[str]:
    bucket_name = s3_settings.S3_BUCKET_NAME

    response = await s3_client.list_buckets()
    bucket_exists = bucket_name in [bucket_struct.get("Name") for bucket_struct in response["Buckets"]]
    if bucket_exists:
        await _empty_bucket(s3_client, bucket_name)

    if not bucket_exists:
        await s3_client.create_bucket(Bucket=bucket_name)
    response = await s3_client.list_buckets()
    assert response["Buckets"]
    assert bucket_name in [bucket_struct.get("Name") for bucket_struct in response["Buckets"]], (
        f"failed creating {bucket_name}"
    )

    yield bucket_name

    await _empty_bucket(s3_client, bucket_name)


@pytest.fixture
async def with_bucket_versioning_enabled(s3_client: S3Client, s3_bucket: str) -> str:
    await s3_client.put_bucket_versioning(
        Bucket=s3_bucket,
        VersioningConfiguration={"MFADelete": "Disabled", "Status": "Enabled"},
    )
    return s3_bucket
