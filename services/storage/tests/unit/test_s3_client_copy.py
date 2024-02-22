# pylint: disable=no-name-in-module
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_envs import (
    EnvVarsDict,
    load_dotenv,
    setenvs_from_dict,
)
from simcore_service_storage.application import get_application_settings
from simcore_service_storage.models import S3BucketName
from simcore_service_storage.s3 import get_s3_client
from simcore_service_storage.settings import S3Settings


@pytest.fixture(scope="session")
def external_environment(request: pytest.FixtureRequest) -> EnvVarsDict:
    """
    If a file under test folder prefixed with `.env-secret` is present,
    then this fixture captures it.

    This technique allows reusing the same tests to check against
    external development/production servers
    """
    envs = {}
    if envfile := request.config.getoption("--external-envfile"):
        assert isinstance(envfile, Path)
        print("🚨 EXTERNAL: external envs detected. Loading", envfile, "...")
        envs = load_dotenv(envfile)
        assert "S3_ACCESS_KEY" in envs
        assert "S3_BUCKET_NAME" in envs
    return envs


@pytest.fixture
def mock_config(
    monkeypatch: pytest.MonkeyPatch,
    mocked_s3_server_envs: EnvVarsDict,
    external_environment: EnvVarsDict,
) -> None:
    # NOTE: override services/storage/tests/conftest.py::mock_config

    if external_environment:
        print("WARNING: be careful with running tests that")

    setenvs_from_dict(monkeypatch, {"STORAGE_POSTGRES": "null", **external_environment})
    print(
        "Tests below will be using the following S3 settings:",
        S3Settings.create_from_envs().json(indent=1),
    )


@pytest.fixture
def simcore_bucket_name(client: TestClient) -> str:
    assert client.app
    settings = get_application_settings(client.app)
    assert settings.STORAGE_S3
    return settings.STORAGE_S3.S3_BUCKET_NAME


#
# Concept of marking failed copies
#


async def _mark_copy_start(s3_client, bucket, prefix):
    marker_key = f"{prefix}.copying"
    await s3_client.put_object(Bucket=bucket, Key=marker_key, Body="")


async def _mark_copy_end(s3_client, bucket, prefix):
    # NOTE: there is a risk that if this call fails, the GC will delete good copies!
    marker_key = f"{prefix}.copying"
    await s3_client.delete_object(Bucket=bucket, Key=marker_key)


async def _garbage_collect_failed_copies(s3_client, bucket, prefix, threshold_hours=1):
    marker_key = f"{prefix}.copying"
    try:
        response = await s3_client.get_object(Bucket=bucket, Key=marker_key)
        last_modified = response["LastModified"]
        if datetime.now(timezone.utc) - last_modified > timedelta(
            hours=threshold_hours
        ):
            print(f"Found stale marker. Cleaning up failed copy objects in {prefix}")
            paginator = s3_client.get_paginator("list_objects_v2")
            async for result in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if "Contents" in result:
                    for obj in result["Contents"]:
                        if not obj["Key"].endswith(".copying"):
                            print(f'Deleting {obj["Key"]}')
                            await s3_client.delete_object(Bucket=bucket, Key=obj["Key"])
            # Finally, delete the marker object
            await s3_client.delete_object(Bucket=bucket, Key=marker_key)
    except s3_client.exceptions.NoSuchKey:
        print("No marker found. No cleanup needed.")


async def test_copy_directory_from_s3_to_s3(
    mocker: MockerFixture,
    client: TestClient,
    simcore_bucket_name: S3BucketName,
):
    bytes_transfered_cb = mocker.MagicMock()

    src_fmd_object_name = (
        "d2504240-cf63-11ee-bf70-02420a0b0228"  # andreas example (s4lio)
    )
    # src_fmd_object_name = (
    #    "502fd316-8a9e-11ee-a81b-02420a0b173b"  # taylor example (NIH prod)
    # )
    # src_fmd_object_name = "d0be75f0-ca9a-11ee-9b42-02420a000206"  # MY example (master)
    new_fmd_object_name = "pytest_destination"
    assert client.app
    s3_client = get_s3_client(client.app)

    tic = time.time()
    copied_count, copied_size = await s3_client.copy_directory(
        bucket=simcore_bucket_name,
        src_prefix=src_fmd_object_name,
        dst_prefix=new_fmd_object_name,
        bytes_transfered_cb=bytes_transfered_cb,
    )
    elapsed = time.time() - tic
    print(
        "Copied",
        src_fmd_object_name,
        f"{copied_count=}",
        f"{sum(copied_count)=}",
        f"{copied_size=}",
        f"{sum(copied_size)=}",
        f"{elapsed=:3.2f}",
        "secs",
    )

    # 0be75f0-ca9a-11ee-9b42-02420a000206 copied_count=1004 copied_size=1048579839 elapsed=72.92 secs
    #

    assert bytes_transfered_cb.called
    assert bytes_transfered_cb.call_count == 2 * sum(copied_count)


@pytest.mark.skip(reason="UNDER DEVE")
async def test_it():
    import botocore.exceptions
    from simcore_service_storage.exceptions import S3ReadTimeoutError
    from simcore_service_storage.s3_utils import (
        on_timeout_retry_with_exponential_backoff,
    )

    for key, value in sorted(botocore.exceptions.__dict__.items()):
        if isinstance(value, type):
            print(key)

    with pytest.raises(S3ReadTimeoutError) as err_info:
        raise S3ReadTimeoutError(
            error=botocore.exceptions.ReadTimeoutError(
                endpoint_url="https://foo.endpoint.com", request="foo", response="bar"
            )
        )

    print(err_info.value)
    assert isinstance(err_info.value.error, botocore.exceptions.ReadTimeoutError)

    async def foo():
        raise S3ReadTimeoutError(
            error=botocore.exceptions.ReadTimeoutError(
                endpoint_url="https://failing.point.com", request="foo", response="bar"
            )
        )

    foo_with_retry = on_timeout_retry_with_exponential_backoff(foo)

    with pytest.raises(S3ReadTimeoutError):
        await foo_with_retry()

    print(foo_with_retry.retry.statistics)
    assert foo_with_retry.retry.statistics["attempt_number"] == 5
