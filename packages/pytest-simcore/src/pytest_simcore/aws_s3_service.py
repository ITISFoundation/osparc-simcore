# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import


import contextlib
import typing

import aioboto3
import pytest
from aiobotocore.session import ClientCreatorContext
from botocore.client import Config
from faker import Faker
from pydantic import parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_docker import get_service_published_port
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from pytest_simcore.helpers.utils_host import get_localhost_ip
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
    await s3_client.create_bucket(Bucket=bucket_name)
    response = await s3_client.list_buckets()
    assert response["Buckets"]
    assert bucket_name in [
        bucket_struct.get("Name") for bucket_struct in response["Buckets"]
    ], f"failed creating {bucket_name}"

    return bucket_name


@pytest.fixture(scope="module")
def minio_s3_settings(
    docker_stack: dict,
    testing_environ_vars: dict,
    monkeypatch_module: pytest.MonkeyPatch,
) -> S3Settings:
    assert "pytest-ops_minio" in docker_stack["services"]

    return S3Settings(
        S3_ACCESS_KEY=testing_environ_vars["S3_ACCESS_KEY"],
        S3_SECRET_KEY=testing_environ_vars["S3_SECRET_KEY"],
        S3_ENDPOINT=f"{get_localhost_ip()}:{get_service_published_port('minio')}",
        S3_SECURE=parse_obj_as(bool, testing_environ_vars["S3_SECURE"]),
        S3_BUCKET_NAME=testing_environ_vars["S3_BUCKET_NAME"],
    )


@pytest.fixture
def minio_s3_settings_envs(
    minio_s3_settings: S3Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    changed_envs: EnvVarsDict = minio_s3_settings.dict(exclude_unset=True)
    return setenvs_from_dict(monkeypatch, changed_envs)
