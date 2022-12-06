# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import botocore.exceptions
import pytest
from fastapi import FastAPI
from moto.server import ThreadedMotoServer
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.core.errors import ConfigurationError
from simcore_service_autoscaling.core.settings import EC2Settings
from simcore_service_autoscaling.modules.ec2 import AutoscalingEC2, get_ec2_client
from types_aiobotocore_ec2 import EC2Client


@pytest.fixture
def ec2_settings(
    app_environment: EnvVarsDict,
) -> EC2Settings:
    return EC2Settings.create_from_envs()


async def test_ec2_client_lifespan(ec2_settings: EC2Settings):
    ec2 = await AutoscalingEC2.create(settings=ec2_settings)
    assert ec2
    assert ec2.client
    assert ec2.exit_stack
    assert ec2.session

    await ec2.close()


async def test_ec2_client_raises_when_no_connection_available(ec2_client: EC2Client):
    with pytest.raises(
        botocore.exceptions.ClientError, match=r".+ AWS was not able to validate .+"
    ):
        await ec2_client.describe_account_attributes(DryRun=True)


async def test_ec2_client_with_mock_server(
    mocked_aws_server_envs: None, ec2_client: EC2Client
):
    # passes without exception
    await ec2_client.describe_account_attributes(DryRun=True)


@pytest.fixture
def disabled_ec2(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("EC2_ACCESS_KEY_ID")


async def test_ec2_does_not_initialize_if_deactivated(
    disabled_rabbitmq: None, disabled_ec2: None, initialized_app: FastAPI
):
    assert hasattr(initialized_app.state, "ec2_client")
    assert initialized_app.state.ec2_client == None
    with pytest.raises(ConfigurationError):
        get_ec2_client(initialized_app)


async def test_ec2_client_when_ec2_server_goes_up_and_down(
    mocked_aws_server: ThreadedMotoServer,
    mocked_aws_server_envs: None,
    ec2_client: EC2Client,
):
    # passes without exception
    await ec2_client.describe_account_attributes(DryRun=True)
    mocked_aws_server.stop()
    with pytest.raises(botocore.exceptions.EndpointConnectionError):
        await ec2_client.describe_account_attributes(DryRun=True)

    # restart
    mocked_aws_server.start()
    # passes without exception
    await ec2_client.describe_account_attributes(DryRun=True)
