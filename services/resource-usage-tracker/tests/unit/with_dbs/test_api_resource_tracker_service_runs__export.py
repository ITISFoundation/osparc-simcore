from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from moto.server import ThreadedMotoServer
from pydantic import AnyUrl, parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import service_runs

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]

_USER_ID = 1


@pytest.fixture
def enable_resource_usage_tracker_s3(monkeypatch):
    # Set the environment variable
    monkeypatch.setenv("RESOURCE_USAGE_TRACKER_S3_ENABLED", "1")


@pytest.fixture
async def mocked_export(mocker: MockerFixture):
    mock_export = mocker.patch(
        "simcore_service_resource_usage_tracker.services.resource_tracker_service_runs.ResourceTrackerRepository.export_service_runs_table_to_s3",
        autospec=True,
    )

    return mock_export


@pytest.fixture
async def mocked_presigned_link(mocker: MockerFixture):
    mock_presigned_link = mocker.patch(
        "simcore_service_resource_usage_tracker.services.resource_tracker_service_runs.SimcoreS3API.create_presigned_download_link",
        return_value=parse_obj_as(
            AnyUrl,
            "https://www.testing.com/",
        ),
    )

    return mock_presigned_link


@pytest.mark.rpc_test()
async def test_rpc_list_service_runs_which_was_billed(
    enable_resource_usage_tracker_s3,
    mocked_aws_server: ThreadedMotoServer,
    mocked_s3_server_envs: EnvVarsDict,
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
    assert isinstance(download_url, AnyUrl)
    assert mocked_export.called
    assert mocked_presigned_link.called
