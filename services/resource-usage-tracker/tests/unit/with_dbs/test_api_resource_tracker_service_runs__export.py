# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import os
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy as sa
from moto.server import ThreadedMotoServer
from pydantic import AnyUrl, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import service_runs
from settings_library.s3 import S3Settings
from types_aiobotocore_s3 import S3Client

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]

_USER_ID = 1


@pytest.fixture
async def mocked_export(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_resource_usage_tracker.services.service_runs.ResourceTrackerRepository.export_service_runs_table_to_s3",
        autospec=True,
    )


@pytest.fixture
async def mocked_presigned_link(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_resource_usage_tracker.services.service_runs.SimcoreS3API.create_single_presigned_download_link",
        return_value=TypeAdapter(AnyUrl).validate_python("https://www.testing.com/"),
    )


@pytest.fixture
async def enable_resource_usage_tracker_s3(
    mock_env: EnvVarsDict,
    mocked_aws_server: ThreadedMotoServer,
    mocked_s3_server_envs: EnvVarsDict,
    mocked_s3_server_settings: S3Settings,
    s3_client: S3Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Create bucket
    await s3_client.create_bucket(Bucket=mocked_s3_server_settings.S3_BUCKET_NAME)

    # Remove the environment variable
    if "RESOURCE_USAGE_TRACKER_S3" in os.environ:
        monkeypatch.delenv("RESOURCE_USAGE_TRACKER_S3")


@pytest.mark.rpc_test()
async def test_rpc_list_service_runs_which_was_billed(
    enable_resource_usage_tracker_s3: None,
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    rpc_client: RabbitMQRPCClient,
    mocked_export: Mock,
    mocked_presigned_link: Mock,
):
    download_url = await service_runs.export_service_runs(
        rpc_client,
        user_id=_USER_ID,
        product_name="osparc",
    )
    assert isinstance(download_url, AnyUrl)  # nosec
    assert mocked_export.called
    assert mocked_presigned_link.called
