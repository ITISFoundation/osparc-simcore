# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

import asyncio
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from aiobotocore.session import AioBaseClient, get_session
from aiohttp import ClientResponse, ClientSession, TCPConnector
from aioresponses import aioresponses
from faker import Faker
from models_library.api_schemas_storage import (
    FileUploadLinks,
    FileUploadSchema,
    UploadedPart,
)
from models_library.basic_types import IDStr
from moto.server import ThreadedMotoServer
from pydantic import AnyUrl, ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from servicelib.aiohttp import status
from servicelib.progress_bar import ProgressBarData
from simcore_sdk.node_ports_common.exceptions import AwsS3BadRequestRequestTimeoutError
from simcore_sdk.node_ports_common.file_io_utils import (
    _check_for_aws_http_errors,
    _ExtendedClientResponseError,
    _process_batch,
    _raise_for_status,
    upload_file_to_presigned_links,
)

A_TEST_ROUTE = "http://a-fake-address:1249/test-route"


@pytest.fixture
async def client_session() -> AsyncIterable[ClientSession]:
    async with ClientSession(connector=TCPConnector(force_close=True)) as session:
        yield session


async def test_raise_for_status(
    aioresponses_mocker: aioresponses, client_session: ClientSession
):
    aioresponses_mocker.get(
        A_TEST_ROUTE, body="OPSIE there was an error here", status=400
    )

    async with client_session.get(A_TEST_ROUTE) as resp:
        assert isinstance(resp, ClientResponse)

        with pytest.raises(_ExtendedClientResponseError) as exe_info:
            await _raise_for_status(resp)
        assert "OPSIE there was an error here" in f"{exe_info.value}"


@dataclass
class _TestParams:
    will_retry: bool
    status_code: int
    body: str = ""


@pytest.mark.parametrize(
    "test_params",
    [
        _TestParams(will_retry=True, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR),
        _TestParams(will_retry=True, status_code=status.HTTP_503_SERVICE_UNAVAILABLE),
        _TestParams(will_retry=False, status_code=status.HTTP_400_BAD_REQUEST),
        _TestParams(will_retry=False, status_code=status.HTTP_200_OK),
        _TestParams(will_retry=False, status_code=399),
    ],
)
async def test_check_for_aws_http_errors(
    aioresponses_mocker: aioresponses,
    client_session: ClientSession,
    test_params: _TestParams,
):
    aioresponses_mocker.get(
        A_TEST_ROUTE, body=test_params.body, status=test_params.status_code
    )

    async with client_session.get(A_TEST_ROUTE) as resp:
        try:
            await _raise_for_status(resp)
        except _ExtendedClientResponseError as exception:
            assert (  # noqa: PT017
                _check_for_aws_http_errors(exception) is test_params.will_retry
            )


async def test_process_batch_captures_400_request_timeout_and_wraps_in_error(
    aioresponses_mocker: aioresponses, client_session: ClientSession
):
    async def _mock_upload_task() -> None:
        body = (
            '<?xml version="1.0" encoding="UTF-8"?><Error><Code>RequestTimeout</Code>'
            "<Message>Your socket connection to the server was not read from or written to within "
            "the timeout period. Idle connections will be closed.</Message>"
            "<RequestId>7EE901348D6C6812</RequestId><HostId>"
            "FfQE7jdbUt39E6mcQq/"
            "ZeNR52ghjv60fccNT4gCE4IranXjsGLG+L6FUyiIxx1tAuXL9xtz2NAY7ZlbzMTm94fhY3TBiCBmf"
            "</HostId></Error>"
        )
        aioresponses_mocker.get(A_TEST_ROUTE, body=body, status=400)

        async with client_session.get(A_TEST_ROUTE) as resp:
            # raises like _session_put does
            await _raise_for_status(resp)

    with pytest.raises(AwsS3BadRequestRequestTimeoutError):
        await _process_batch(
            upload_tasks=[_mock_upload_task()],
            max_concurrency=1,
            file_name="mock_file",
            file_size=1,
            file_chunk_size=1,
            last_chunk_size=1,
        )


async def test_upload_file_to_presigned_links_raises_aws_s3_400_request_time_out_error(
    mocker: MockerFixture,
    create_upload_links: Callable[[int, ByteSize], Awaitable[FileUploadSchema]],
    create_file_of_size: Callable[[ByteSize], Path],
    faker: Faker,
):
    file_size = ByteSize(1)
    upload_links = await create_upload_links(1, file_size)

    mocker.patch(
        "simcore_sdk.node_ports_common.file_io_utils._upload_file_part",
        side_effect=AwsS3BadRequestRequestTimeoutError(body="nothing"),
    )

    async with ProgressBarData(num_steps=1, description=faker.pystr()) as progress_bar:
        with pytest.raises(AwsS3BadRequestRequestTimeoutError):
            await upload_file_to_presigned_links(
                session=AsyncMock(),
                file_upload_links=upload_links,
                file_to_upload=create_file_of_size(file_size),
                num_retries=0,
                io_log_redirect_cb=None,
                progress_bar=progress_bar,
            )


@pytest.fixture
async def aiobotocore_s3_client(
    mocked_aws_server: ThreadedMotoServer,
) -> AsyncIterator[AioBaseClient]:
    session = get_session()
    async with session.create_client(
        "s3",
        endpoint_url=f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access
        aws_secret_access_key="xxx",
        aws_access_key_id="xxx",
    ) as client:
        yield client


async def _clean_bucket_content(s3_client: AioBaseClient, bucket: str):
    response = await s3_client.list_objects_v2(Bucket=bucket)
    while response["KeyCount"] > 0:
        await s3_client.delete_objects(
            Bucket=bucket,
            Delete={
                "Objects": [
                    {"Key": obj["Key"]} for obj in response["Contents"] if "Key" in obj
                ]
            },
        )
        response = await s3_client.list_objects_v2(Bucket=bucket)


@pytest.fixture
async def bucket(aiobotocore_s3_client: AioBaseClient, faker: Faker) -> str:
    response = await aiobotocore_s3_client.create_bucket(Bucket=faker.pystr())
    assert "ResponseMetadata" in response
    assert "HTTPStatusCode" in response["ResponseMetadata"]
    assert response["ResponseMetadata"]["HTTPStatusCode"] == status.HTTP_200_OK

    response = await aiobotocore_s3_client.list_buckets()
    assert response["Buckets"]
    assert len(response["Buckets"]) == 1
    bucket_name = response["Buckets"][0]["Name"]
    yield bucket_name
    await _clean_bucket_content(aiobotocore_s3_client, bucket_name)


@pytest.fixture
def file_id(faker: Faker) -> str:
    return faker.pystr()


@pytest.fixture
async def create_upload_links(
    mocked_aws_server: ThreadedMotoServer,
    aiobotocore_s3_client: AioBaseClient,
    faker: Faker,
    bucket: str,
    file_id: str,
) -> AsyncIterator[Callable[[int, ByteSize], Awaitable[FileUploadSchema]]]:
    file_id = "fake2"

    async def _creator(num_upload_links: int, chunk_size: ByteSize) -> FileUploadSchema:
        response = await aiobotocore_s3_client.create_multipart_upload(
            Bucket=bucket, Key=file_id
        )
        assert "UploadId" in response
        upload_id = response["UploadId"]

        upload_links = TypeAdapter(list[AnyUrl]).validate_python(
            await asyncio.gather(
                *[
                    aiobotocore_s3_client.generate_presigned_url(
                        "upload_part",
                        Params={
                            "Bucket": bucket,
                            "Key": file_id,
                            "PartNumber": i + 1,
                            "UploadId": upload_id,
                        },
                    )
                    for i in range(num_upload_links)
                ],
            ),
        )

        return FileUploadSchema(
            chunk_size=chunk_size,
            urls=upload_links,
            links=FileUploadLinks(
                abort_upload=TypeAdapter(AnyUrl).validate_python(faker.uri()),
                complete_upload=TypeAdapter(AnyUrl).validate_python(faker.uri()),
            ),
        )

    return _creator


@pytest.mark.skip(reason="this will allow to reproduce an issue")
@pytest.mark.parametrize(
    "file_size,used_chunk_size",
    [
        (
            TypeAdapter(ByteSize).validate_python(21800510238),
            TypeAdapter(ByteSize).validate_python(10485760),
        )
    ],
)
async def test_upload_file_to_presigned_links(
    client_session: ClientSession,
    create_upload_links: Callable[[int, ByteSize], Awaitable[FileUploadSchema]],
    create_file_of_size: Callable[[ByteSize], Path],
    file_size: ByteSize,
    used_chunk_size: ByteSize,
    faker: Faker,
):
    """This test is here to reproduce the issue https://github.com/ITISFoundation/osparc-simcore/issues/3531
    One theory is that something might be wrong in how the chunking is done and that AWS times out
    as it is waiting for more data.

    Until this can be reproduced this shall stay here.
    Mind also this link https://github.com/aws/aws-sdk-js/issues/281 where it seems removing the Content-length header helped:
    this could be done and tested by: packages/simcore-sdk/src/simcore_sdk/node_ports_common/file_io_utils.py:274-276

    For this we need the EXACT size of the file that is uploaded. Therefore according changes to output the size
    in bytes of the problematic file were added.
    """
    local_file = create_file_of_size(file_size)
    num_links = 2080
    effective_chunk_size = TypeAdapter(ByteSize).validate_python(
        local_file.stat().st_size / num_links
    )
    assert effective_chunk_size <= used_chunk_size
    upload_links = await create_upload_links(num_links, used_chunk_size)
    assert len(upload_links.urls) == num_links
    async with ProgressBarData(num_steps=1, description=IDStr("")) as progress_bar:
        uploaded_parts: list[UploadedPart] = await upload_file_to_presigned_links(
            session=client_session,
            file_upload_links=upload_links,
            file_to_upload=local_file,
            num_retries=0,
            io_log_redirect_cb=None,
            progress_bar=progress_bar,
        )
    assert progress_bar._current_steps == pytest.approx(1)  # noqa: SLF001
    assert uploaded_parts
