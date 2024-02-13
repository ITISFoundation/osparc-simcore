# pylint: disable=no-name-in-module
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

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


async def test__copy_path_s3_s3(
    mocker: MockerFixture,
    client: TestClient,
    simcore_bucket_name: S3BucketName,
):
    bytes_transfered_cb = mocker.MagicMock()

    src_fmd_object_name = "502fd316-8a9e-11ee-a81b-02420a0b173b"
    new_fmd_object_name = "destination"
    assert client.app
    s3_client = get_s3_client(client.app)

    start = 1
    async for page in s3_client.iter_pages(
        simcore_bucket_name,
        prefix=src_fmd_object_name,
    ):
        objects_names_map: dict[str, str] = {
            s3_obj[
                "Key"
            ]: f"{new_fmd_object_name}{s3_obj['Key'].removeprefix(src_fmd_object_name)}"
            for s3_obj in page
        }
        for s3_obj in page:
            print(s3_obj)

        n = 0
        for n, (src, new) in enumerate(objects_names_map.items(), start=start):
            print(n, "copy_file", src, "->", new)
        start += n + 1
        #     # NOTE: copy_file cannot be called concurrently or it will hang.
        #     # test this with copying multiple 1GB files if you do not believe me
        #     await s3_client.copy_file(
        #         simcore_bucket_name,
        #         cast(SimcoreS3FileID, src),
        #         cast(SimcoreS3FileID, new),
        #         bytes_transfered_cb=bytes_transfered_cb,
        #     )

        #     assert bytes_transfered_cb.called


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
