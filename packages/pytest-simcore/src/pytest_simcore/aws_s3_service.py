import contextlib
import typing

import aioboto3
import pytest
from aiobotocore.session import ClientCreatorContext
from types_aiobotocore_s3 import S3Client


@pytest.fixture
async def s3_client(
    mocked_ec2_server_settings: EC2Settings,
) -> typing.AsyncIterator[S3Client]:
    session = aioboto3.Session()
    exit_stack = contextlib.AsyncExitStack()
    session_client = session.client(
        "ec2",
        endpoint_url=mocked_ec2_server_settings.EC2_ENDPOINT,
        aws_access_key_id=mocked_ec2_server_settings.EC2_ACCESS_KEY_ID,
        aws_secret_access_key=mocked_ec2_server_settings.EC2_SECRET_ACCESS_KEY,
        region_name=mocked_ec2_server_settings.EC2_REGION_NAME,
    )
    assert isinstance(session_client, ClientCreatorContext)
    ec2_client = typing.cast(
        S3Client, await exit_stack.enter_async_context(session_client)
    )

    yield ec2_client

    await exit_stack.aclose()
