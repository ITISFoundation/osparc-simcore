# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import dataclasses
from collections.abc import AsyncIterator

import botocore.exceptions
import pytest
from aws_library.ssm import SimcoreSSMAPI, SSMInvalidCommandIdError
from faker import Faker
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


@pytest.fixture
def fake_command_id(faker: Faker) -> str:
    return faker.pystr(min_chars=36, max_chars=36)


async def test_get_command(
    mocked_aws_server: ThreadedMotoServer,
    simcore_ssm_api: SimcoreSSMAPI,
    faker: Faker,
    fake_command_id: str,
):
    with pytest.raises(SSMInvalidCommandIdError):
        await simcore_ssm_api.get_command(faker.pystr(), command_id=fake_command_id)


async def test_send_command(
    mocked_aws_server: ThreadedMotoServer, simcore_ssm_api: SimcoreSSMAPI, faker: Faker
):
    command_name = faker.word()
    target_instance_id = faker.pystr()
    sent_command = await simcore_ssm_api.send_command(
        instance_ids=[target_instance_id],
        command=faker.text(),
        command_name=command_name,
    )
    assert sent_command
    assert sent_command.command_id
    assert sent_command.name == command_name
    assert sent_command.instance_ids == [target_instance_id]
    assert sent_command.status == "Success"

    got = await simcore_ssm_api.get_command(
        target_instance_id, command_id=sent_command.command_id
    )
    assert dataclasses.asdict(got) == {
        **dataclasses.asdict(sent_command),
        "message": "Success",
    }


async def test_is_instance_connected_to_ssm_server(
    mocked_aws_server: ThreadedMotoServer, simcore_ssm_api: SimcoreSSMAPI
):
    ...


async def test_wait_for_has_instance_completed_cloud_init(
    mocked_aws_server: ThreadedMotoServer, simcore_ssm_api: SimcoreSSMAPI
):
    ...
