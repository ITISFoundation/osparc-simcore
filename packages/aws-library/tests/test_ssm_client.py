# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from collections.abc import AsyncIterator

import botocore.exceptions
import pytest
from aws_library.ssm._client import SimcoreSSMAPI
from moto.server import ThreadedMotoServer
from settings_library.ssm import SSMSettings
from types_aiobotocore_ssm import SSMClient


@pytest.fixture
async def simcore_ssm_api(
    mocked_ssm_server_settings: SSMSettings,
) -> AsyncIterator[SimcoreSSMAPI]:
    ec2 = await SimcoreSSMAPI.create(settings=mocked_ssm_server_settings)
    assert ec2
    assert ec2.client
    assert ec2.exit_stack
    assert ec2.session
    yield ec2
    await ec2.close()


async def test_ssm_client_lifespan(simcore_ssm_api: SimcoreSSMAPI):
    ...


async def test_aiobotocore_ssm_client_when_ssm_server_goes_up_and_down(
    mocked_aws_server: ThreadedMotoServer,
    ssm_client: SSMClient,
):
    # passes without exception
    await ssm_client.list_commands(MaxResults=1)
    mocked_aws_server.stop()
    with pytest.raises(botocore.exceptions.EndpointConnectionError):
        await ssm_client.list_commands(MaxResults=1)

    # restart
    mocked_aws_server.start()
    # passes without exception
    await ssm_client.list_commands(MaxResults=1)


async def test_ping(
    mocked_aws_server: ThreadedMotoServer,
    simcore_ssm_api: SimcoreSSMAPI,
):
    assert await simcore_ssm_api.ping() is True
    mocked_aws_server.stop()
    assert await simcore_ssm_api.ping() is False
    mocked_aws_server.start()
    assert await simcore_ssm_api.ping() is True
