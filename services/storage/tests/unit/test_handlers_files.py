# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


import asyncio
import filecmp
import json
import urllib.parse
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import AsyncContextManager, Literal
from uuid import uuid4

import pytest
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestClient
from aiopg.sa import Engine
from faker import Faker
from models_library.api_schemas_storage import (
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadCompletionBody,
    FileUploadSchema,
    LinkType,
    PresignedLink,
    SoftCopyBody,
    UploadedPart,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID, NodeID, SimcoreS3FileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyHttpUrl, ByteSize, parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_parametrizations import byte_size_ids
from simcore_service_storage.constants import (
    MULTIPART_UPLOADS_MIN_TOTAL_SIZE,
    S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID,
)
from simcore_service_storage.exceptions import S3KeyNotFoundError
from simcore_service_storage.handlers_files import UPLOAD_TASKS_KEY
from simcore_service_storage.models import S3BucketName, UploadID
from simcore_service_storage.s3_client import StorageS3Client
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from tests.helpers.file_utils import upload_file_part, upload_file_to_presigned_link
from tests.helpers.utils_file_meta_data import assert_file_meta_data_in_db
from yarl import URL

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


_HTTP_PRESIGNED_LINK_QUERY_KEYS = [
    "X-Amz-Algorithm",
    "X-Amz-Credential",
    "X-Amz-Date",
    "X-Amz-Expires",
    "X-Amz-Signature",
    "X-Amz-SignedHeaders",
]


async def assert_multipart_uploads_in_progress(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    file_id: SimcoreS3FileID,
    *,
    expected_upload_ids: list[str] | None,
):
    """if None is passed, then it checks that no uploads are in progress"""
    list_uploads: list[
        tuple[UploadID, SimcoreS3FileID]
    ] = await storage_s3_client.list_ongoing_multipart_uploads(bucket=storage_s3_bucket)
    if expected_upload_ids is None:
        assert (
            not list_uploads
        ), f"expected NO multipart uploads in progress, got {list_uploads}"
    else:
        for upload_id, _ in list_uploads:
            assert (
                upload_id in expected_upload_ids
            ), f"{upload_id=} is in progress but was not expected!"


@dataclass
class SingleLinkParam:
    url_query: dict[str, str]
    expected_link_scheme: Literal["s3"] | Literal["http"]
    expected_link_query_keys: list[str]
    expected_chunk_size: ByteSize


@pytest.mark.parametrize(
    "single_link_param",
    [
        pytest.param(
            SingleLinkParam(
                {},
                "http",
                _HTTP_PRESIGNED_LINK_QUERY_KEYS,
                parse_obj_as(ByteSize, "5GiB"),
            ),
            id="default_returns_single_presigned",
        ),
        pytest.param(
            SingleLinkParam(
                {"link_type": "presigned"},
                "http",
                _HTTP_PRESIGNED_LINK_QUERY_KEYS,
                parse_obj_as(ByteSize, "5GiB"),
            ),
            id="presigned_returns_single_presigned",
        ),
        pytest.param(
            SingleLinkParam(
                {"link_type": "s3"}, "s3", [], parse_obj_as(ByteSize, "5TiB")
            ),
            id="s3_returns_single_s3_link",
        ),
    ],
)
async def test_create_upload_file_with_file_size_0_returns_single_link(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    simcore_file_id: SimcoreS3FileID,
    single_link_param: SingleLinkParam,
    aiopg_engine: Engine,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    cleanup_user_projects_file_metadata: None,
):
    # create upload file link
    received_file_upload = await create_upload_file_link_v2(
        simcore_file_id, **(single_link_param.url_query | {"file_size": 0})
    )
    # check links, there should be only 1
    assert len(received_file_upload.urls) == 1
    assert received_file_upload.urls[0].scheme == single_link_param.expected_link_scheme
    assert received_file_upload.urls[0].path
    assert received_file_upload.urls[0].path.endswith(
        f"{urllib.parse.quote(simcore_file_id, safe='/')}"
    )
    # the chunk_size
    assert received_file_upload.chunk_size == single_link_param.expected_chunk_size
    if single_link_param.expected_link_query_keys:
        assert received_file_upload.urls[0].query
        query = {
            query_str.split("=")[0]: query_str.split("=")[1]
            for query_str in received_file_upload.urls[0].query.split("&")
        }
        for key in single_link_param.expected_link_query_keys:
            assert key in query
    else:
        assert not received_file_upload.urls[0].query

    # now check the entry in the database is correct, there should be only one
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=bool(single_link_param.expected_link_scheme == "s3"),
        expected_upload_expiration_date=True,
    )
    # check that no s3 multipart upload was initiated
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        simcore_file_id,
        expected_upload_ids=None,
    )


@pytest.mark.parametrize(
    "single_link_param",
    [
        pytest.param(
            SingleLinkParam(
                {},
                "http",
                _HTTP_PRESIGNED_LINK_QUERY_KEYS,
                parse_obj_as(ByteSize, "5GiB"),
            ),
            id="default_returns_single_presigned",
        ),
        pytest.param(
            SingleLinkParam(
                {"link_type": "presigned"},
                "http",
                _HTTP_PRESIGNED_LINK_QUERY_KEYS,
                parse_obj_as(ByteSize, "5GiB"),
            ),
            id="presigned_returns_single_presigned",
        ),
        pytest.param(
            SingleLinkParam(
                {"link_type": "s3"}, "s3", [], parse_obj_as(ByteSize, "5TiB")
            ),
            id="s3_returns_single_s3_link",
        ),
    ],
)
async def test_create_upload_file_with_no_file_size_query_returns_v1_structure(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    simcore_file_id: SimcoreS3FileID,
    single_link_param: SingleLinkParam,
    aiopg_engine: Engine,
    create_upload_file_link_v1: Callable[..., Awaitable[PresignedLink]],
    cleanup_user_projects_file_metadata: None,
):
    # create upload file link
    received_file_upload_link = await create_upload_file_link_v1(
        simcore_file_id, **(single_link_param.url_query)
    )
    # check links, there should be only 1
    assert received_file_upload_link.link
    assert (
        received_file_upload_link.link.scheme == single_link_param.expected_link_scheme
    )
    assert received_file_upload_link.link.path
    assert received_file_upload_link.link.path.endswith(
        f"{urllib.parse.quote(simcore_file_id, safe='/')}"
    )
    # now check the entry in the database is correct, there should be only one
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=bool(single_link_param.expected_link_scheme == "s3"),
        expected_upload_expiration_date=True,
    )
    # check that no s3 multipart upload was initiated
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        simcore_file_id,
        expected_upload_ids=None,
    )


@dataclass(frozen=True)
class MultiPartParam:
    link_type: LinkType
    file_size: ByteSize
    expected_response: type[web.HTTPException]
    expected_num_links: int
    expected_chunk_size: ByteSize


@pytest.mark.parametrize(
    "test_param",
    [
        pytest.param(
            MultiPartParam(
                link_type=LinkType.PRESIGNED,
                file_size=parse_obj_as(ByteSize, "10MiB"),
                expected_response=web.HTTPOk,
                expected_num_links=1,
                expected_chunk_size=parse_obj_as(ByteSize, "10MiB"),
            ),
            id="10MiB file,presigned",
        ),
        pytest.param(
            MultiPartParam(
                link_type=LinkType.PRESIGNED,
                file_size=parse_obj_as(ByteSize, "100MiB"),
                expected_response=web.HTTPOk,
                expected_num_links=10,
                expected_chunk_size=parse_obj_as(ByteSize, "10MiB"),
            ),
            id="100MiB file,presigned",
        ),
        pytest.param(
            MultiPartParam(
                link_type=LinkType.PRESIGNED,
                file_size=parse_obj_as(ByteSize, "5TiB"),
                expected_response=web.HTTPOk,
                expected_num_links=8739,
                expected_chunk_size=parse_obj_as(ByteSize, "600MiB"),
            ),
            id="5TiB file,presigned",
        ),
        pytest.param(
            MultiPartParam(
                link_type=LinkType.PRESIGNED,
                file_size=parse_obj_as(ByteSize, "9431773844"),
                expected_response=web.HTTPOk,
                expected_num_links=900,
                expected_chunk_size=parse_obj_as(ByteSize, "10MiB"),
            ),
            id="9431773844B (8.8Gib) file,presigned",
        ),
        pytest.param(
            MultiPartParam(
                link_type=LinkType.S3,
                file_size=parse_obj_as(ByteSize, "255GiB"),
                expected_response=web.HTTPOk,
                expected_num_links=1,
                expected_chunk_size=parse_obj_as(ByteSize, "255GiB"),
            ),
            id="5TiB file,s3",
        ),
    ],
)
async def test_create_upload_file_presigned_with_file_size_returns_multipart_links_if_bigger_than_99MiB(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    simcore_file_id: SimcoreS3FileID,
    test_param: MultiPartParam,
    aiopg_engine: Engine,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    cleanup_user_projects_file_metadata: None,
):
    # create upload file link
    received_file_upload = await create_upload_file_link_v2(
        simcore_file_id,
        link_type=test_param.link_type.value.lower(),
        file_size=f"{test_param.file_size}",
    )
    # number of links
    assert (
        len(received_file_upload.urls) == test_param.expected_num_links
    ), f"{len(received_file_upload.urls)} vs {test_param.expected_num_links=}"
    # all links are unique
    assert len(set(received_file_upload.urls)) == len(received_file_upload.urls)
    assert received_file_upload.chunk_size == test_param.expected_chunk_size

    # now check the entry in the database is correct, there should be only one
    expect_upload_id = bool(test_param.file_size >= MULTIPART_UPLOADS_MIN_TOTAL_SIZE)
    upload_id: UploadID | None = await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=expect_upload_id,
        expected_upload_expiration_date=True,
    )

    # check that the s3 multipart upload was initiated properly
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        simcore_file_id,
        expected_upload_ids=([upload_id] if upload_id else None),
    )


@pytest.mark.parametrize(
    "link_type, file_size",
    [
        (LinkType.PRESIGNED, parse_obj_as(ByteSize, "1000Mib")),
        (LinkType.S3, parse_obj_as(ByteSize, "1000Mib")),
    ],
    ids=byte_size_ids,
)
async def test_delete_unuploaded_file_correctly_cleans_up_db_and_s3(
    aiopg_engine: Engine,
    client: TestClient,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    simcore_file_id: SimcoreS3FileID,
    link_type: LinkType,
    file_size: ByteSize,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    user_id: UserID,
    location_id: LocationID,
):
    assert client.app
    # create upload file link
    upload_link = await create_upload_file_link_v2(
        simcore_file_id, link_type=link_type.value.lower(), file_size=file_size
    )
    expect_upload_id = bool(file_size >= MULTIPART_UPLOADS_MIN_TOTAL_SIZE)
    # we shall have an entry in the db, waiting for upload
    upload_id = await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=expect_upload_id,
        expected_upload_expiration_date=True,
    )

    # check that the s3 multipart upload was initiated properly
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        simcore_file_id,
        expected_upload_ids=([upload_id] if upload_id else None),
    )
    # delete/abort file upload
    abort_url = URL(upload_link.links.abort_upload).relative()
    response = await client.post(f"{abort_url}")
    await assert_status(response, web.HTTPNoContent)

    # the DB shall be cleaned up
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=simcore_file_id,
        expected_entry_exists=False,
        expected_file_size=None,
        expected_upload_id=None,
        expected_upload_expiration_date=None,
    )
    # the multipart upload shall be aborted
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        simcore_file_id,
        expected_upload_ids=None,
    )


@pytest.mark.parametrize(
    "link_type, file_size",
    [
        (LinkType.PRESIGNED, parse_obj_as(ByteSize, "10Mib")),
        (LinkType.PRESIGNED, parse_obj_as(ByteSize, "1000Mib")),
        (LinkType.S3, parse_obj_as(ByteSize, "10Mib")),
        (LinkType.S3, parse_obj_as(ByteSize, "1000Mib")),
    ],
    ids=byte_size_ids,
)
async def test_upload_same_file_uuid_aborts_previous_upload(
    aiopg_engine: Engine,
    client: TestClient,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    simcore_file_id: SimcoreS3FileID,
    link_type: LinkType,
    file_size: ByteSize,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
):
    assert client.app
    # create upload file link
    file_upload_link = await create_upload_file_link_v2(
        simcore_file_id, link_type=link_type.value.lower(), file_size=file_size
    )
    expect_upload_id = bool(
        file_size >= MULTIPART_UPLOADS_MIN_TOTAL_SIZE or link_type == LinkType.S3
    )
    # we shall have an entry in the db, waiting for upload
    upload_id = await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=expect_upload_id,
        expected_upload_expiration_date=True,
    )

    # check that the s3 multipart upload was initiated properly
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        simcore_file_id,
        expected_upload_ids=([upload_id] if upload_id else None),
    )

    # now we create a new upload, in case it was a multipart,
    # we should abort the previous upload to prevent unwanted costs
    await asyncio.sleep(1)
    new_file_upload_link = await create_upload_file_link_v2(
        simcore_file_id, link_type=link_type.value.lower(), file_size=file_size
    )
    if link_type == LinkType.PRESIGNED:
        assert file_upload_link != new_file_upload_link
    else:
        assert file_upload_link == new_file_upload_link
    # we shall have an entry in the db, waiting for upload
    new_upload_id = await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=expect_upload_id,
        expected_upload_expiration_date=True,
    )
    if expect_upload_id and link_type == LinkType.PRESIGNED:
        assert (
            upload_id != new_upload_id
        ), "There shall be a new upload id after a new call to create_upload_file"
    elif expect_upload_id and link_type == LinkType.S3:
        assert upload_id == new_upload_id
        assert upload_id == S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID

    # check that the s3 multipart upload was initiated properly
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        simcore_file_id,
        expected_upload_ids=([new_upload_id] if new_upload_id else None),
    )


@pytest.fixture
def complex_file_name(faker: Faker) -> str:
    return f"subfolder_1/sub_folder 2/some file name with spaces and special characters  -_ü!öäàé+|}} {{3245_{faker.file_name()}"


@pytest.mark.parametrize(
    "file_size",
    [
        (parse_obj_as(ByteSize, "1Mib")),
        (parse_obj_as(ByteSize, "500Mib")),
        pytest.param(parse_obj_as(ByteSize, "7Gib"), marks=pytest.mark.heavy_load),
    ],
    ids=byte_size_ids,
)
async def test_upload_real_file(
    complex_file_name: str,
    file_size: ByteSize,
    upload_file: Callable[[ByteSize, str], Awaitable[Path]],
):
    await upload_file(file_size, complex_file_name)


@pytest.mark.parametrize(
    "file_size",
    [
        (parse_obj_as(ByteSize, "1Mib")),
        (parse_obj_as(ByteSize, "117Mib")),
    ],
    ids=byte_size_ids,
)
async def test_upload_real_file_with_emulated_storage_restart_after_completion_was_called(
    complex_file_name: str,
    file_size: ByteSize,
    client: TestClient,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    location_id: LocationID,
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    aiopg_engine: Engine,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
):
    """what does that mean?
    storage runs the completion tasks in the background,
    if after running the completion task, storage restarts then the task is lost.
    Nevertheless the client still has a reference to the completion future and shall be able
    to ask for its status"""
    assert client.app
    file = create_file_of_size(file_size, complex_file_name)
    file_id = create_simcore_file_id(project_id, node_id, complex_file_name)
    file_upload_link = await create_upload_file_link_v2(
        file_id, link_type="presigned", file_size=file_size
    )
    # upload the file
    part_to_etag: list[UploadedPart] = await upload_file_to_presigned_link(
        file, file_upload_link
    )
    # complete the upload
    complete_url = URL(file_upload_link.links.complete_upload).relative()
    response = await client.post(
        f"{complete_url}",
        json=jsonable_encoder(FileUploadCompletionBody(parts=part_to_etag)),
    )
    response.raise_for_status()
    data, error = await assert_status(response, web.HTTPAccepted)
    assert not error
    assert data
    file_upload_complete_response = FileUploadCompleteResponse.parse_obj(data)
    state_url = URL(file_upload_complete_response.links.state).relative()

    # here we do not check now for the state completion. instead we simulate a restart where the tasks disappear
    client.app[UPLOAD_TASKS_KEY].clear()
    # now check for the completion
    completion_etag = None
    async for attempt in AsyncRetrying(
        reraise=True,
        wait=wait_fixed(1),
        stop=stop_after_delay(60),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            print(
                f"--> checking for upload {state_url=}, {attempt.retry_state.attempt_number}..."
            )
            response = await client.post(f"{state_url}")
            data, error = await assert_status(response, web.HTTPOk)
            assert not error
            assert data
            future = FileUploadCompleteFutureResponse.parse_obj(data)
            assert future.state == FileUploadCompleteState.OK
            assert future.e_tag is not None
            completion_etag = future.e_tag
            print(
                f"--> done waiting, data is completely uploaded [{attempt.retry_state.retry_object.statistics}]"
            )
    # check the entry in db now has the correct file size, and the upload id is gone
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=file_id,
        expected_entry_exists=True,
        expected_file_size=file_size,
        expected_upload_id=False,
        expected_upload_expiration_date=False,
    )
    # check the file is in S3 for real
    s3_metadata = await storage_s3_client.get_file_metadata(storage_s3_bucket, file_id)
    assert s3_metadata.size == file_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag == completion_etag


async def test_upload_of_single_presigned_link_lazily_update_database_on_get(
    aiopg_engine: Engine,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    client: TestClient,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    project_id: ProjectID,
    node_id: NodeID,
    faker: Faker,
    get_file_meta_data: Callable[..., Awaitable[FileMetaDataGet]],
):
    assert client.app
    file_size = parse_obj_as(ByteSize, "500Mib")
    file_name = faker.file_name()
    # create a file
    file = create_file_of_size(file_size, file_name)
    simcore_file_id = create_simcore_file_id(project_id, node_id, file_name)
    # get an S3 upload link
    file_upload_link = await create_upload_file_link_v2(
        simcore_file_id, link_type="s3", file_size=file_size
    )
    # let's use the storage s3 internal client to upload
    with file.open("rb") as fp:
        response = await storage_s3_client.client.put_object(
            Bucket=storage_s3_bucket, Key=simcore_file_id, Body=fp
        )
        assert "ETag" in response
        upload_e_tag = json.loads(response["ETag"])
    # check the file is now on S3
    s3_metadata = await storage_s3_client.get_file_metadata(
        storage_s3_bucket, simcore_file_id
    )
    assert s3_metadata.size == file_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag == upload_e_tag
    # check getting the file actually lazily updates the table and returns the expected values
    received_fmd: FileMetaDataGet = await get_file_meta_data(simcore_file_id)
    assert received_fmd.entity_tag == upload_e_tag


async def test_upload_real_file_with_s3_client(
    aiopg_engine: Engine,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    client: TestClient,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    project_id: ProjectID,
    node_id: NodeID,
    faker: Faker,
    get_file_meta_data: Callable[..., Awaitable[FileMetaDataGet]],
):
    assert client.app
    file_size = parse_obj_as(ByteSize, "500Mib")
    file_name = faker.file_name()
    # create a file
    file = create_file_of_size(file_size, file_name)
    simcore_file_id = create_simcore_file_id(project_id, node_id, file_name)
    # get an S3 upload link
    file_upload_link = await create_upload_file_link_v2(
        simcore_file_id, link_type="s3", file_size=file_size
    )
    # let's use the storage s3 internal client to upload
    with file.open("rb") as fp:
        response = await storage_s3_client.client.put_object(
            Bucket=storage_s3_bucket, Key=simcore_file_id, Body=fp
        )
        assert "ETag" in response
        upload_e_tag = json.loads(response["ETag"])
    # check the file is now on S3
    s3_metadata = await storage_s3_client.get_file_metadata(
        storage_s3_bucket, simcore_file_id
    )
    assert s3_metadata.size == file_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag == upload_e_tag

    # complete the upload
    complete_url = URL(file_upload_link.links.complete_upload).relative()
    start = perf_counter()
    print(f"--> completing upload of {file=}")
    response = await client.post(f"{complete_url}", json={"parts": []})
    response.raise_for_status()
    data, error = await assert_status(response, web.HTTPAccepted)
    assert not error
    assert data
    file_upload_complete_response = FileUploadCompleteResponse.parse_obj(data)
    state_url = URL(file_upload_complete_response.links.state).relative()
    completion_etag = None
    async for attempt in AsyncRetrying(
        reraise=True,
        wait=wait_fixed(1),
        stop=stop_after_delay(60),
        retry=retry_if_exception_type(ValueError),
    ):
        with attempt:
            print(
                f"--> checking for upload {state_url=}, {attempt.retry_state.attempt_number}..."
            )
            response = await client.post(f"{state_url}")
            response.raise_for_status()
            data, error = await assert_status(response, web.HTTPOk)
            assert not error
            assert data
            future = FileUploadCompleteFutureResponse.parse_obj(data)
            if future.state != FileUploadCompleteState.OK:
                raise ValueError(f"{data=}")
            assert future.state == FileUploadCompleteState.OK
            assert future.e_tag is not None
            completion_etag = future.e_tag
            print(
                f"--> done waiting, data is completely uploaded [{attempt.retry_state.retry_object.statistics}]"
            )

    print(f"--> completed upload in {perf_counter() - start}")

    # check the entry in db now has the correct file size, and the upload id is gone
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=file_size,
        expected_upload_id=False,
        expected_upload_expiration_date=False,
    )
    # check the file is in S3 for real
    s3_metadata = await storage_s3_client.get_file_metadata(
        storage_s3_bucket, simcore_file_id
    )
    assert s3_metadata.size == file_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag == completion_etag


@pytest.mark.parametrize(
    "file_size",
    [parse_obj_as(ByteSize, "160Mib"), parse_obj_as(ByteSize, "1Mib")],
    ids=byte_size_ids,
)
async def test_upload_twice_and_fail_second_time_shall_keep_first_version(
    aiopg_engine: Engine,
    client: TestClient,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    file_size: ByteSize,
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    faker: Faker,
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    user_id: UserID,
    location_id: LocationID,
):
    assert client.app
    # 1. upload a valid file
    file_name = faker.file_name()
    _, uploaded_file_id = await upload_file(file_size, file_name)

    # 2. create an upload link for the second file
    upload_link = await create_upload_file_link_v2(
        uploaded_file_id, link_type="presigned", file_size=file_size
    )
    # we shall have an entry in the db, waiting for upload
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=uploaded_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=bool(file_size >= MULTIPART_UPLOADS_MIN_TOTAL_SIZE),
        expected_upload_expiration_date=True,
    )

    # 3. upload part of the file to simulate a network issue in the upload
    new_file = create_file_of_size(file_size, file_name)
    with pytest.raises(RuntimeError):
        async with ClientSession() as session:
            await upload_file_part(
                session,
                new_file,
                part_index=1,
                file_offset=0,
                this_file_chunk_size=file_size,
                num_parts=1,
                upload_url=upload_link.urls[0],
                raise_while_uploading=True,
            )

    # 4. abort file upload
    abort_url = URL(upload_link.links.abort_upload).relative()
    response = await client.post(f"{abort_url}")
    await assert_status(response, web.HTTPNoContent)

    # we should have the original file still in now...
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=uploaded_file_id,
        expected_entry_exists=True,
        expected_file_size=file_size,
        expected_upload_id=False,
        expected_upload_expiration_date=False,
    )
    # check the file is in S3 for real
    s3_metadata = await storage_s3_client.get_file_metadata(
        storage_s3_bucket, uploaded_file_id
    )
    assert s3_metadata.size == file_size


@pytest.mark.parametrize(
    "file_size",
    [
        pytest.param(parse_obj_as(ByteSize, "1Mib")),
    ],
    ids=byte_size_ids,
)
async def test_download_file(
    client: TestClient,
    file_size: ByteSize,
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    location_id: int,
    user_id: UserID,
    tmp_path: Path,
    faker: Faker,
):
    assert client.app
    uploaded_file, uploaded_file_uuid = await upload_file(file_size, faker.file_name())

    download_url = (
        client.app.router["download_file"]
        .url_for(
            location_id=f"{location_id}",
            file_id=urllib.parse.quote(uploaded_file_uuid, safe=""),
        )
        .with_query(user_id=user_id)
    )
    response = await client.get(f"{download_url}")
    data, error = await assert_status(response, web.HTTPOk)
    assert not error
    assert data
    assert "link" in data
    # now download the link from S3
    dest_file = tmp_path / faker.file_name()
    async with ClientSession() as session:
        response = await session.get(data["link"])
        response.raise_for_status()
        with dest_file.open("wb") as fp:
            fp.write(await response.read())
    assert dest_file.exists()
    # compare files
    assert filecmp.cmp(uploaded_file, dest_file)


@pytest.mark.parametrize(
    "file_size",
    [
        pytest.param(parse_obj_as(ByteSize, "1")),
    ],
    ids=byte_size_ids,
)
async def test_download_file_cases(
    client: TestClient,
    file_size: ByteSize,
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    location_id: int,
    project_id: ProjectID,
    node_id: NodeID,
    user_id: UserID,
    create_empty_directory: Callable[..., Awaitable[FileUploadSchema]],
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
):
    assert client.app

    # 1. error case
    # no file was not uploaded
    missing_file = parse_obj_as(SimcoreS3FileID, f"{project_id}/{node_id}/missing.file")
    assert (
        await storage_s3_client.file_exists(storage_s3_bucket, s3_object=missing_file)
        is False
    )

    download_url = (
        client.app.router["download_file"]
        .url_for(
            location_id=f"{location_id}",
            file_id=urllib.parse.quote(missing_file, safe=""),
        )
        .with_query(user_id=user_id)
    )
    response = await client.get(f"{download_url}")
    data, error = await assert_status(response, web.HTTPNotFound)
    assert data is None
    assert missing_file in error["message"]

    # 2. file_meta_data entry corresponds to a file
    # upload a single file as a file_meta_data entry and check link
    _, uploaded_file_uuid = await upload_file(file_size, "meta_data_entry_is_file.file")
    assert (
        await storage_s3_client.file_exists(
            storage_s3_bucket, s3_object=uploaded_file_uuid
        )
        is True
    )

    download_url = (
        client.app.router["download_file"]
        .url_for(
            location_id=f"{location_id}",
            file_id=urllib.parse.quote(uploaded_file_uuid, safe=""),
        )
        .with_query(user_id=user_id)
    )
    response = await client.get(f"{download_url}")
    data, error = await assert_status(response, web.HTTPOk)
    assert not error
    assert data
    assert "link" in data
    assert parse_obj_as(AnyHttpUrl, data["link"])

    # 3. file_meta_data entry corresponds to a directory
    # upload a file inside a directory and check the download link

    directory_name = "a-test-dir"
    directory_file_upload = await create_empty_directory(directory_name)

    assert directory_file_upload.urls[0].path
    dir_path_in_s3 = directory_file_upload.urls[0].path.strip("/")

    file_name = "meta_data_entry_is_dir.file"
    file = create_file_of_size(file_size, file_name)

    s3_file_id = parse_obj_as(SimcoreS3FileID, f"{dir_path_in_s3}/{file_name}")
    await storage_s3_client.upload_file(storage_s3_bucket, file, s3_file_id, None)
    assert (
        await storage_s3_client.file_exists(storage_s3_bucket, s3_object=s3_file_id)
        is True
    )

    # finally check the download link
    download_url = (
        client.app.router["download_file"]
        .url_for(
            location_id=f"{location_id}",
            file_id=urllib.parse.quote(s3_file_id, safe=""),
        )
        .with_query(user_id=user_id)
    )
    response = await client.get(f"{download_url}")
    data, error = await assert_status(response, web.HTTPOk)
    assert not error
    assert data
    assert "link" in data
    assert parse_obj_as(AnyHttpUrl, data["link"])

    # 4. file_meta_data entry corresponds to a directory but file is not present in directory

    missing_s3_file_id = parse_obj_as(
        SimcoreS3FileID, f"{dir_path_in_s3}/missing_inside_dir.file"
    )
    download_url = (
        client.app.router["download_file"]
        .url_for(
            location_id=f"{location_id}",
            file_id=urllib.parse.quote(missing_s3_file_id, safe=""),
        )
        .with_query(user_id=user_id)
    )
    response = await client.get(f"{download_url}")
    data, error = await assert_status(response, web.HTTPNotFound)
    assert data is None
    assert missing_s3_file_id in error["message"]


@pytest.mark.parametrize(
    "file_size",
    [
        pytest.param(parse_obj_as(ByteSize, "1Mib")),
    ],
    ids=byte_size_ids,
)
async def test_delete_file(
    aiopg_engine: Engine,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    client: TestClient,
    file_size: ByteSize,
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    location_id: int,
    user_id: UserID,
    faker: Faker,
):
    assert client.app
    _, uploaded_file_uuid = await upload_file(file_size, faker.file_name())

    delete_url = (
        client.app.router["delete_file"]
        .url_for(
            location_id=f"{location_id}",
            file_id=urllib.parse.quote(uploaded_file_uuid, safe=""),
        )
        .with_query(user_id=user_id)
    )
    response = await client.delete(f"{delete_url}")
    await assert_status(response, web.HTTPNoContent)

    # check the entry in db is removed
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=uploaded_file_uuid,
        expected_entry_exists=False,
        expected_file_size=None,
        expected_upload_id=None,
        expected_upload_expiration_date=None,
    )
    # check the file is gone from S3
    with pytest.raises(S3KeyNotFoundError):
        await storage_s3_client.get_file_metadata(storage_s3_bucket, uploaded_file_uuid)


async def test_copy_as_soft_link(
    client: TestClient,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
):
    assert client.app

    # missing simcore_file_id returns 404
    missing_file_uuid = create_simcore_file_id(project_id, node_id, faker.file_name())
    invalid_link_id = create_simcore_file_id(uuid4(), uuid4(), faker.file_name())
    url = (
        client.app.router["copy_as_soft_link"]
        .url_for(
            file_id=urllib.parse.quote(missing_file_uuid, safe=""),
        )
        .with_query(user_id=user_id)
    )
    response = await client.post(
        f"{url}", json=jsonable_encoder(SoftCopyBody(link_id=invalid_link_id))
    )
    await assert_status(response, web.HTTPNotFound)

    # now let's try with whatever link id
    file, original_file_uuid = await upload_file(
        parse_obj_as(ByteSize, "10Mib"), faker.file_name()
    )
    url = (
        client.app.router["copy_as_soft_link"]
        .url_for(
            file_id=urllib.parse.quote(original_file_uuid, safe=""),
        )
        .with_query(user_id=user_id)
    )
    link_id = SimcoreS3FileID(f"api/{node_id}/{faker.file_name()}")
    response = await client.post(
        f"{url}", json=jsonable_encoder(SoftCopyBody(link_id=link_id))
    )
    data, error = await assert_status(response, web.HTTPOk)
    assert not error
    fmd = parse_obj_as(FileMetaDataGet, data)
    assert fmd.file_id == link_id


@pytest.fixture
async def create_empty_directory(
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    client: TestClient,
    project_id: ProjectID,
    node_id: NodeID,
) -> Callable[..., Awaitable[FileUploadSchema]]:
    async def _directory_creator(dir_name: str):
        # creating an empty directory goes through the same procedure as uploading a multipart file
        # done by using 3 calls:
        # 1. create the link as a directory
        # 2. call complete_upload link
        # 3. call file_upload_complete_response until it replies OK

        directory_file_id = create_simcore_file_id(project_id, node_id, dir_name)
        directory_file_upload: FileUploadSchema = await create_upload_file_link_v2(
            directory_file_id, link_type="s3", is_directory="true", file_size=-1
        )
        # always returns a v2 link when dealing with directories
        assert isinstance(directory_file_upload, FileUploadSchema)
        assert len(directory_file_upload.urls) == 1

        # complete the upload
        complete_url = URL(directory_file_upload.links.complete_upload).relative()
        response = await client.post(
            f"{complete_url}",
            json=jsonable_encoder(FileUploadCompletionBody(parts=[])),
        )
        response.raise_for_status()
        data, error = await assert_status(response, web.HTTPAccepted)
        assert not error
        assert data
        file_upload_complete_response = FileUploadCompleteResponse.parse_obj(data)
        state_url = URL(file_upload_complete_response.links.state).relative()

        # check that it finished updating

        client.app[UPLOAD_TASKS_KEY].clear()
        # now check for the completion
        async for attempt in AsyncRetrying(
            reraise=True,
            wait=wait_fixed(1),
            stop=stop_after_delay(60),
            retry=retry_if_exception_type(AssertionError),
        ):
            with attempt:
                print(
                    f"--> checking for upload {state_url=}, {attempt.retry_state.attempt_number}..."
                )
                response = await client.post(f"{state_url}")
                data, error = await assert_status(response, web.HTTPOk)
                assert not error
                assert data
                future = FileUploadCompleteFutureResponse.parse_obj(data)
                assert future.state == FileUploadCompleteState.OK
                assert future.e_tag is None
                print(
                    f"--> done waiting, data is completely uploaded [{attempt.retry_state.retry_object.statistics}]"
                )

        return directory_file_upload

    return _directory_creator


@pytest.fixture
async def populate_directory(
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    project_id: ProjectID,
    node_id: NodeID,
) -> Callable[..., Awaitable[None]]:
    async def _create_content(
        file_size_in_dir: ByteSize,
        dir_name: str,
        subdir_count: int = 4,
        file_count: int = 5,
    ) -> None:
        file = create_file_of_size(file_size_in_dir, "some_file")

        async def _create_file(s: int, f: int):
            file_name = f"{dir_name}/sub-dir-{s}/file-{f}"
            clean_path = Path(f"{project_id}/{node_id}/{file_name}")
            await storage_s3_client.upload_file(
                storage_s3_bucket, file, SimcoreS3FileID(f"{clean_path}"), None
            )

        tasks: deque = deque()
        for s in range(subdir_count):
            for f in range(file_count):
                tasks.append(_create_file(s, f))

        await asyncio.gather(*tasks)

        file.unlink()

    return _create_content


@pytest.fixture
async def delete_directory(
    client: TestClient,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    user_id: UserID,
    location_id: LocationID,
) -> Callable[..., Awaitable[None]]:
    async def _dir_remover(directory_file_upload: FileUploadSchema) -> None:
        directory_file_id = directory_file_upload.urls[0].path.strip("/")
        delete_url = (
            client.app.router["delete_file"]
            .url_for(
                location_id=f"{location_id}",
                file_id=urllib.parse.quote(directory_file_id, safe=""),
            )
            .with_query(user_id=user_id)
        )
        response = await client.delete(f"{delete_url}")
        await assert_status(response, web.HTTPNoContent)

        # NOTE: ensures no more files are left in the directory,
        # even if one file is left this will detect it
        files = await storage_s3_client.list_files(
            bucket=storage_s3_bucket, prefix=directory_file_id
        )
        assert len(files) == 0

    return _dir_remover


@pytest.fixture
async def directory_with_files(
    create_empty_directory: Callable[..., Awaitable[FileUploadSchema]],
    populate_directory: Callable[..., Awaitable[None]],
    delete_directory: Callable[..., Awaitable[None]],
) -> Callable[..., AsyncContextManager[FileUploadSchema]]:
    @asynccontextmanager
    async def _context_manager(
        dir_name: str, file_size_in_dir: ByteSize, subdir_count: int, file_count: int
    ) -> AsyncIterator[FileUploadSchema]:
        directory_file_upload: FileUploadSchema = await create_empty_directory(
            dir_name=dir_name
        )

        await populate_directory(
            file_size_in_dir=file_size_in_dir,
            dir_name=dir_name,
            subdir_count=subdir_count,
            file_count=file_count,
        )

        yield directory_file_upload

        await delete_directory(directory_file_upload=directory_file_upload)

    return _context_manager


async def __list_files(
    client: TestClient,
    user_id: UserID,
    location_id: LocationID,
    *,
    path: str,
    expand_dirs: bool,
) -> list[FileMetaDataGet]:
    get_url = (
        client.app.router["get_files_metadata"]
        .url_for(
            location_id=f"{location_id}",
            file_id=urllib.parse.quote(path, safe=""),
        )
        .with_query(user_id=user_id, expand_dirs=f"{expand_dirs}".lower())
    )
    response = await client.get(f"{get_url}")
    data, error = await assert_status(response, web.HTTPOk)
    assert not error
    return parse_obj_as(list[FileMetaDataGet], data)


async def _list_files_legacy(
    client: TestClient,
    user_id: UserID,
    location_id: LocationID,
    directory_file_upload: FileUploadSchema,
) -> list[FileMetaDataGet]:
    directory_file_id = directory_file_upload.urls[0].path.strip("/")
    return await __list_files(
        client, user_id, location_id, path=directory_file_id, expand_dirs=True
    )


async def _list_files_and_directories(
    client: TestClient,
    user_id: UserID,
    location_id: LocationID,
    directory_file_upload: FileUploadSchema,
) -> list[FileMetaDataGet]:
    directory_parent_path = Path(directory_file_upload.urls[0].path).parent
    directory_file_id = f"{directory_parent_path}".strip("/")
    return await __list_files(
        client, user_id, location_id, path=directory_file_id, expand_dirs=False
    )


@pytest.mark.parametrize("link_type", LinkType)
@pytest.mark.parametrize(
    "file_size",
    [
        parse_obj_as(ByteSize, "-1"),
        parse_obj_as(ByteSize, "0"),
        parse_obj_as(ByteSize, "1TB"),
    ],
)
async def test_is_directory_link_forces_link_type_and_size(
    project_id: ProjectID,
    node_id: NodeID,
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    client: TestClient,
    location_id: LocationID,
    user_id: UserID,
    link_type: LinkType,
    file_size: ByteSize,
):
    DIR_NAME = "some-dir"
    directory_file_id = create_simcore_file_id(project_id, node_id, DIR_NAME)
    directory_file_upload: FileUploadSchema = await create_upload_file_link_v2(
        directory_file_id,
        link_type=link_type.value.lower(),
        is_directory="true",
        file_size=file_size,
    )
    # only gets 1 link regardless of size
    assert len(directory_file_upload.urls) == 1

    files_and_directories: list[FileMetaDataGet] = await _list_files_and_directories(
        client, user_id, location_id, directory_file_upload
    )
    assert len(files_and_directories) == 1
    assert files_and_directories[0].is_directory is True
    # file size is -1 meaning unknown
    assert files_and_directories[0].file_size == -1


async def test_ensure_expand_dirs_defaults_true(
    mocker: MockerFixture,
    client: TestClient,
    user_id: UserID,
    location_id: int,
):
    mocked_object = mocker.patch(
        "simcore_service_storage.simcore_s3_dsm.SimcoreS3DataManager.list_files",
        autospec=True,
    )

    get_url = (
        client.app.router["get_files_metadata"]
        .url_for(
            location_id=f"{location_id}",
            file_id=urllib.parse.quote("mocked_path", safe=""),
        )
        .with_query(user_id=user_id)
    )
    await client.get(f"{get_url}")

    assert len(mocked_object.call_args_list) == 1
    call_args_list = mocked_object.call_args_list[0]
    assert "expand_dirs" in call_args_list.kwargs
    assert call_args_list.kwargs["expand_dirs"] is True


async def test_upload_file_is_directory_and_remove_content(
    create_empty_directory: Callable[..., Awaitable[FileUploadSchema]],
    populate_directory: Callable[..., Awaitable[None]],
    delete_directory: Callable[..., Awaitable[None]],
    client: TestClient,
    location_id: LocationID,
    user_id: UserID,
):
    FILE_SIZE_IN_DIR = parse_obj_as(ByteSize, "1Mib")
    DIR_NAME = "some-dir"
    SUBDIR_COUNT = 4
    FILE_COUNT = 5

    # DIRECTORY CREATION (is empty)

    directory_file_upload: FileUploadSchema = await create_empty_directory(
        dir_name=DIR_NAME
    )

    files_and_directories: list[FileMetaDataGet] = await _list_files_and_directories(
        client, user_id, location_id, directory_file_upload
    )
    assert len(files_and_directories) == 1

    list_of_files: list[FileMetaDataGet] = await _list_files_legacy(
        client, user_id, location_id, directory_file_upload
    )
    assert len(list_of_files) == 0

    # DIRECTORY WITH CONTENT

    await populate_directory(
        file_size_in_dir=FILE_SIZE_IN_DIR,
        dir_name=DIR_NAME,
        subdir_count=SUBDIR_COUNT,
        file_count=FILE_COUNT,
    )

    files_and_directories: list[FileMetaDataGet] = await _list_files_and_directories(
        client, user_id, location_id, directory_file_upload
    )
    assert len(files_and_directories) == 1

    list_of_files: list[FileMetaDataGet] = await _list_files_legacy(
        client, user_id, location_id, directory_file_upload
    )
    assert len(list_of_files) == SUBDIR_COUNT * FILE_COUNT

    # DIRECTORY REMOVAL

    await delete_directory(directory_file_upload=directory_file_upload)

    list_of_files: list[FileMetaDataGet] = await _list_files_legacy(
        client, user_id, location_id, directory_file_upload
    )
    assert len(list_of_files) == 0

    files_and_directories: list[FileMetaDataGet] = await _list_files_and_directories(
        client, user_id, location_id, directory_file_upload
    )
    assert len(files_and_directories) == 0


@pytest.mark.parametrize("files_in_dir", [1002])
async def test_listing_more_than_1000_objects_in_bucket(
    directory_with_files: Callable[..., AsyncContextManager[FileUploadSchema]],
    client: TestClient,
    location_id: LocationID,
    user_id: UserID,
    files_in_dir: int,
):
    async with directory_with_files(
        dir_name="some-random",
        file_size_in_dir=parse_obj_as(ByteSize, "1"),
        subdir_count=1,
        file_count=files_in_dir,
    ) as directory_file_upload:
        list_of_files: list[FileMetaDataGet] = await _list_files_legacy(
            client, user_id, location_id, directory_file_upload
        )
        # for now no more than 1000 objects will be returned
        assert len(list_of_files) == 1000
