# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging

import botocore.exceptions
import pytest
from aws_library.ec2._error_handler import ec2_exception_handler
from aws_library.ec2._errors import EC2NotConnectedError, EC2RuntimeError, EC2TimeoutError
from pytest_mock import MockerFixture


class _FakeClient:
    def __init__(self, *, raises: Exception) -> None:
        self._raises = raises

    @ec2_exception_handler(logging.getLogger(__name__))
    async def some_method(self) -> None:
        raise self._raises


async def test_ec2_exception_handler_maps_waiter_error():
    client = _FakeClient(
        raises=botocore.exceptions.WaiterError(name="instance_exists", reason="timeout", last_response={})
    )

    with pytest.raises(EC2TimeoutError):
        await client.some_method()


async def test_ec2_exception_handler_maps_endpoint_connection_error():
    client = _FakeClient(raises=botocore.exceptions.EndpointConnectionError(endpoint_url="http://example.com"))

    with pytest.raises(EC2NotConnectedError):
        await client.some_method()


async def test_ec2_exception_handler_maps_botocore_error_and_logs_it(mocker: MockerFixture):
    logger_exception = mocker.patch("logging.Logger.exception")
    client = _FakeClient(raises=botocore.exceptions.BotoCoreError())

    with pytest.raises(EC2RuntimeError):
        await client.some_method()

    logger_exception.assert_called_once()
