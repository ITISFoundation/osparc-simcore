# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from typing import AsyncIterator, Iterator

import pytest
from aiobotocore.session import get_session
from aiohttp.test_utils import unused_port
from moto.server import ThreadedMotoServer
from pytest_simcore.helpers.utils_docker import get_localhost_ip


@pytest.fixture(scope="module")
def mocked_s3_server() -> Iterator[ThreadedMotoServer]:
    """creates a moto-server that emulates AWS services in place
    NOTE: Never use a bucket with underscores it fails!!
    """
    server = ThreadedMotoServer(ip_address=get_localhost_ip(), port=unused_port())
    # pylint: disable=protected-access
    print(f"--> started mock S3 server on {server._ip_address}:{server._port}")
    print(
        f"--> Dashboard available on [http://{server._ip_address}:{server._port}/moto-api/]"
    )
    server.start()
    yield server
    server.stop()
    print(f"<-- stopped mock S3 server on {server._ip_address}:{server._port}")


async def _clean_bucket_content(aiobotore_s3_client, bucket: str):
    response = await aiobotore_s3_client.list_objects_v2(Bucket=bucket)
    while response["KeyCount"] > 0:
        await aiobotore_s3_client.delete_objects(
            Bucket=bucket,
            Delete={
                "Objects": [
                    {"Key": obj["Key"]} for obj in response["Contents"] if "Key" in obj
                ]
            },
        )
        response = await aiobotore_s3_client.list_objects_v2(Bucket=bucket)


async def _remove_all_buckets(aiobotore_s3_client):
    response = await aiobotore_s3_client.list_buckets()
    bucket_names = [
        bucket["Name"] for bucket in response["Buckets"] if "Name" in bucket
    ]
    await asyncio.gather(
        *(_clean_bucket_content(aiobotore_s3_client, bucket) for bucket in bucket_names)
    )
    await asyncio.gather(
        *(aiobotore_s3_client.delete_bucket(Bucket=bucket) for bucket in bucket_names)
    )


@pytest.fixture
async def mocked_s3_server_envs(
    mocked_s3_server: ThreadedMotoServer, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("S3_SECURE", "false")
    monkeypatch.setenv(
        "S3_ENDPOINT",
        f"{mocked_s3_server._ip_address}:{mocked_s3_server._port}",  # pylint: disable=protected-access
    )
    monkeypatch.setenv("S3_ACCESS_KEY", "xxx")
    monkeypatch.setenv("S3_SECRET_KEY", "xxx")
    monkeypatch.setenv("S3_BUCKET_NAME", "pytestbucket")

    yield

    # cleanup the buckets
    session = get_session()
    async with session.create_client(
        "s3",
        endpoint_url=f"http://{mocked_s3_server._ip_address}:{mocked_s3_server._port}",  # pylint: disable=protected-access
        aws_secret_access_key="xxx",
        aws_access_key_id="xxx",
    ) as client:
        await _remove_all_buckets(client)
