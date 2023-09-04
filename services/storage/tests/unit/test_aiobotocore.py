# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiobotocore.session import get_session
from botocore import exceptions as boto_exceptions
from moto.server import ThreadedMotoServer


async def test_s3_client_fails_if_no_s3():
    """this tests shows that initializing the client actually checks if the S3 server is connected"""
    session = get_session()
    with pytest.raises(boto_exceptions.ClientError):
        async with session.create_client(
            "s3",
            aws_secret_access_key="xxx",  # noqa: S106
            aws_access_key_id="xxx",
        ) as client:
            await client.list_buckets()
    with pytest.raises(boto_exceptions.ClientError):
        async with session.create_client(
            "s3",
            aws_secret_access_key="xxx",  # noqa: S106
            aws_access_key_id="xxx",
        ) as client:
            await client.list_buckets()


async def test_s3_client_reconnects_if_s3_server_restarts(
    mocked_s3_server: ThreadedMotoServer,
):
    """this tests shows that we do not need to restart the client if the S3 server restarts"""
    session = get_session()
    # pylint: disable=protected-access
    async with session.create_client(
        "s3",
        endpoint_url=f"http://{mocked_s3_server._ip_address}:{mocked_s3_server._port}",  # noqa: SLF001
        aws_secret_access_key="xxx",  # noqa: S106
        aws_access_key_id="xxx",
    ) as client:
        assert client
        response = await client.list_buckets()
        assert response
        assert "Buckets" in response
        assert isinstance(response["Buckets"], list)
        assert not response["Buckets"]

        # stop the server, the client shall be unhappy
        mocked_s3_server.stop()
        with pytest.raises(boto_exceptions.EndpointConnectionError):
            response = await client.list_buckets()

        # restart the server and check that the aiobotocore client is connected again
        mocked_s3_server.start()
        response = await client.list_buckets()
        assert response
        assert "Buckets" in response
        assert isinstance(response["Buckets"], list)
        assert not response["Buckets"]
