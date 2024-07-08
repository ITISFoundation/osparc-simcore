# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import contextlib
from collections.abc import AsyncIterator
from typing import cast

import aioboto3
import pytest
from aiobotocore.session import ClientCreatorContext
from pytest_mock.plugin import MockerFixture
from settings_library.ssm import SSMSettings
from types_aiobotocore_ssm.client import SSMClient


@pytest.fixture
async def ssm_client(
    mocked_ssm_server_settings: SSMSettings,
    mocker: MockerFixture,
) -> AsyncIterator[SSMClient]:
    session = aioboto3.Session()
    exit_stack = contextlib.AsyncExitStack()
    session_client = session.client(
        "ssm",
        endpoint_url=mocked_ssm_server_settings.SSM_ENDPOINT,
        aws_access_key_id=mocked_ssm_server_settings.SSM_ACCESS_KEY_ID,
        aws_secret_access_key=mocked_ssm_server_settings.SSM_SECRET_ACCESS_KEY,
        region_name=mocked_ssm_server_settings.SSM_REGION_NAME,
    )
    assert isinstance(session_client, ClientCreatorContext)
    ec2_client = cast(SSMClient, await exit_stack.enter_async_context(session_client))

    yield ec2_client

    await exit_stack.aclose()
