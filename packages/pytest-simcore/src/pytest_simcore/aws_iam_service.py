# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import contextlib
import logging
from collections.abc import AsyncIterator
from typing import cast

import aioboto3
import pytest
from aiobotocore.session import ClientCreatorContext
from faker import Faker
from settings_library.ec2 import EC2Settings
from types_aiobotocore_iam.client import IAMClient

from .helpers.logging_tools import log_context


@pytest.fixture
async def iam_client(
    ec2_settings: EC2Settings,
) -> AsyncIterator[IAMClient]:
    session = aioboto3.Session()
    exit_stack = contextlib.AsyncExitStack()
    session_client = session.client(
        "iam",
        endpoint_url=ec2_settings.EC2_ENDPOINT,
        aws_access_key_id=ec2_settings.EC2_ACCESS_KEY_ID,
        aws_secret_access_key=ec2_settings.EC2_SECRET_ACCESS_KEY,
        region_name=ec2_settings.EC2_REGION_NAME,
    )
    assert isinstance(session_client, ClientCreatorContext)
    iam_client = cast(IAMClient, await exit_stack.enter_async_context(session_client))

    yield iam_client

    await exit_stack.aclose()


@pytest.fixture
async def aws_instance_profile(iam_client: IAMClient, faker: Faker) -> AsyncIterator[str]:
    profile = await iam_client.create_instance_profile(
        InstanceProfileName=faker.pystr(),
    )
    profile_arn = profile["InstanceProfile"]["Arn"]
    with log_context(logging.INFO, msg=f"Created InstanceProfile in AWS with {profile_arn=}"):
        yield profile_arn

    await iam_client.delete_instance_profile(InstanceProfileName=profile["InstanceProfile"]["InstanceProfileName"])
