# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import dataclasses
from collections.abc import AsyncIterator

import botocore.exceptions
import pytest
from aws_library.ssm import (
    SimcoreSSMAPI,
    SSMCommandExecutionResultError,
    SSMCommandExecutionTimeoutError,
    SSMInvalidCommandError,
    SSMNotConnectedError,
)
from aws_library.ssm._client import _AWS_WAIT_NUM_RETRIES
from faker import Faker
from moto.server import ThreadedMotoServer
from pytest_mock.plugin import MockerFixture
from settings_library.ssm import SSMSettings
from types_aiobotocore_ssm import SSMClient


@pytest.fixture
async def simcore_ssm_api(
    mocked_ssm_server_settings: SSMSettings,
) -> AsyncIterator[SimcoreSSMAPI]:
    ec2 = await SimcoreSSMAPI.create(settings=mocked_ssm_server_settings)
    assert ec2
    assert ec2._client
    assert ec2._exit_stack
    assert ec2._session
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


@pytest.fixture
def fake_command_id(faker: Faker) -> str:
    return faker.pystr(min_chars=36, max_chars=36)


async def test_ping(
    mocked_aws_server: ThreadedMotoServer,
    simcore_ssm_api: SimcoreSSMAPI,
    fake_command_id: str,
    faker: Faker,
):
    assert await simcore_ssm_api.ping() is True
    mocked_aws_server.stop()
    assert await simcore_ssm_api.ping() is False
    with pytest.raises(SSMNotConnectedError):
        await simcore_ssm_api.get_command(faker.pystr(), command_id=fake_command_id)
    mocked_aws_server.start()
    assert await simcore_ssm_api.ping() is True


async def test_get_command(
    mocked_aws_server: ThreadedMotoServer,
    simcore_ssm_api: SimcoreSSMAPI,
    faker: Faker,
    fake_command_id: str,
):
    with pytest.raises(SSMInvalidCommandError):
        await simcore_ssm_api.get_command(faker.pystr(), command_id=fake_command_id)


async def test_send_command(
    mocked_aws_server: ThreadedMotoServer,
    simcore_ssm_api: SimcoreSSMAPI,
    faker: Faker,
    fake_command_id: str,
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
    with pytest.raises(SSMInvalidCommandError):
        await simcore_ssm_api.get_command(
            faker.pystr(), command_id=sent_command.command_id
        )
    with pytest.raises(SSMInvalidCommandError):
        await simcore_ssm_api.get_command(
            target_instance_id, command_id=fake_command_id
        )


async def test_is_instance_connected_to_ssm_server(
    mocked_aws_server: ThreadedMotoServer,
    simcore_ssm_api: SimcoreSSMAPI,
    faker: Faker,
    mocker: MockerFixture,
):
    # NOTE: moto does not provide that mock functionality and therefore we mock it ourselves
    mock = mocker.patch(
        "pytest_simcore.helpers.moto._patch_describe_instance_information",
        autospec=True,
        return_value={"InstanceInformationList": [{"PingStatus": "Inactive"}]},
    )
    assert (
        await simcore_ssm_api.is_instance_connected_to_ssm_server(faker.pystr())
        is False
    )
    mock.return_value = {"InstanceInformationList": [{"PingStatus": "Online"}]}
    assert (
        await simcore_ssm_api.is_instance_connected_to_ssm_server(faker.pystr()) is True
    )


async def test_wait_for_has_instance_completed_cloud_init(
    mocked_aws_server: ThreadedMotoServer,
    simcore_ssm_api: SimcoreSSMAPI,
    faker: Faker,
    mocker: MockerFixture,
):
    assert (
        await simcore_ssm_api.wait_for_has_instance_completed_cloud_init(faker.pystr())
        is False
    )
    original_get_command_invocation = (
        simcore_ssm_api._client.get_command_invocation  # noqa: SLF001
    )

    # NOTE: wait_for_has_instance_completed_cloud_init calls twice get_command_invocation
    async def mock_send_command_timesout(*args, **kwargs):
        return {"Status": "Failure", "StatusDetails": faker.text()}

    mocked_command_invocation = mocker.patch.object(
        simcore_ssm_api._client,  # noqa: SLF001
        "get_command_invocation",
        side_effect=mock_send_command_timesout,
    )
    with pytest.raises(SSMCommandExecutionTimeoutError, match="Timed-out"):
        await simcore_ssm_api.wait_for_has_instance_completed_cloud_init(faker.pystr())

    assert mocked_command_invocation.call_count == _AWS_WAIT_NUM_RETRIES

    mocked_command_invocation.reset_mock()
    call_count = 0

    async def mock_wait_command_failed(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return {
                "CommandId": kwargs["CommandId"],
                "Status": "Failure",
                "StatusDetails": faker.text(),
            }
        return await original_get_command_invocation(*args, **kwargs)

    mocked_command_invocation.side_effect = mock_wait_command_failed
    with pytest.raises(SSMCommandExecutionResultError):
        await simcore_ssm_api.wait_for_has_instance_completed_cloud_init(faker.pystr())
    assert mocked_command_invocation.call_count == 2

    # NOTE: default will return False as we need to mock the return value of the cloud-init function
    assert (
        await simcore_ssm_api.wait_for_has_instance_completed_cloud_init(faker.pystr())
        is False
    )

    mocked_command_invocation.reset_mock()
    call_count = 0

    async def mock_wait_command_successful(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return {"Status": "Success", "StandardOutputContent": "status: done\n"}
        return await original_get_command_invocation(*args, **kwargs)

    mocked_command_invocation.side_effect = mock_wait_command_successful
    assert (
        await simcore_ssm_api.wait_for_has_instance_completed_cloud_init(faker.pystr())
        is True
    )
    assert mocked_command_invocation.call_count == 2
