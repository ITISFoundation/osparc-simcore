# pylint:disable=no-name-in-module
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=too-many-positional-arguments
# pylint:disable=unused-argument
# pylint:disable=unused-variable

import asyncio
import filecmp
import json
import logging
import urllib.parse
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from random import choice
from typing import Any, Literal
from uuid import uuid4

import httpx
import pytest
from aiohttp import ClientSession
from aws_library.s3 import S3KeyNotFoundError, S3ObjectKey, SimcoreS3API
from aws_library.s3._constants import MULTIPART_UPLOADS_MIN_TOTAL_SIZE
from celery_library.task_manager import CeleryTaskManager
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_storage.storage_schemas import (
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadSchema,
    LinkType,
    PresignedLink,
    SoftCopyBody,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID, NodeID, SimcoreS3FileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.httpx_assert_checks import assert_status
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.parametrizations import byte_size_ids
from pytest_simcore.helpers.s3 import upload_file_part
from pytest_simcore.helpers.storage_utils import FileIDDict, ProjectWithFilesParams
from pytest_simcore.helpers.storage_utils_file_meta_data import (
    assert_file_meta_data_in_db,
)
from servicelib.aiohttp import status
from simcore_service_storage.constants import S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID
from simcore_service_storage.models import FileDownloadResponse, S3BucketName, UploadID
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from types_aiobotocore_s3 import S3Client
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
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    *,
    expected_upload_ids: list[str] | None,
):
    """if None is passed, then it checks that no uploads are in progress"""
    list_uploads: list[tuple[UploadID, S3ObjectKey]] = (
        await storage_s3_client.list_ongoing_multipart_uploads(bucket=storage_s3_bucket)
    )
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
    expected_link_scheme: Literal["s3", "http"]
    expected_link_query_keys: list[str]
    expected_chunk_size: ByteSize


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "single_link_param",
    [
        pytest.param(
            SingleLinkParam(
                {},
                "http",
                _HTTP_PRESIGNED_LINK_QUERY_KEYS,
                TypeAdapter(ByteSize).validate_python("5GiB"),
            ),
            id="default_returns_single_presigned",
        ),
        pytest.param(
            SingleLinkParam(
                {"link_type": "PRESIGNED"},
                "http",
                _HTTP_PRESIGNED_LINK_QUERY_KEYS,
                TypeAdapter(ByteSize).validate_python("5GiB"),
            ),
            id="presigned_returns_single_presigned",
        ),
        pytest.param(
            SingleLinkParam(
                {"link_type": "S3"},
                "s3",
                [],
                TypeAdapter(ByteSize).validate_python("5TiB"),
            ),
            id="s3_returns_single_s3_link",
        ),
    ],
)
async def test_create_upload_file_with_file_size_0_returns_single_link(
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    simcore_file_id: SimcoreS3FileID,
    single_link_param: SingleLinkParam,
    sqlalchemy_async_engine: AsyncEngine,
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
        sqlalchemy_async_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=bool(single_link_param.expected_link_scheme == "s3"),
        expected_upload_expiration_date=True,
        expected_sha256_checksum=None,
    )
    # check that no s3 multipart upload was initiated
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        expected_upload_ids=None,
    )


@pytest.fixture
async def create_upload_file_link_v1(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    location_id: LocationID,
) -> AsyncIterator[Callable[..., Awaitable[PresignedLink]]]:
    file_params: list[tuple[UserID, int, SimcoreS3FileID]] = []

    async def _link_creator(file_id: SimcoreS3FileID, **query_kwargs) -> PresignedLink:
        url = url_from_operation_id(
            client,
            initialized_app,
            "upload_file",
            location_id=f"{location_id}",
            file_id=file_id,
        ).with_query(**query_kwargs, user_id=user_id)
        assert (
            "file_size" not in url.query
        ), "v1 call to upload_file MUST NOT contain file_size field, this is reserved for v2 call"
        response = await client.put(f"{url}")
        received_file_upload_link, error = assert_status(
            response, status.HTTP_200_OK, PresignedLink
        )
        assert not error
        assert received_file_upload_link
        file_params.append((user_id, location_id, file_id))
        return received_file_upload_link

    yield _link_creator

    # cleanup

    clean_tasks = []
    for u_id, loc_id, file_id in file_params:
        url = url_from_operation_id(
            client,
            initialized_app,
            "upload_file",
            location_id=f"{location_id}",
            file_id=file_id,
        ).with_query(user_id=u_id)
        clean_tasks.append(client.delete(f"{url}"))
    await asyncio.gather(*clean_tasks)


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "single_link_param",
    [
        pytest.param(
            SingleLinkParam(
                {},
                "http",
                _HTTP_PRESIGNED_LINK_QUERY_KEYS,
                TypeAdapter(ByteSize).validate_python("5GiB"),
            ),
            id="default_returns_single_presigned",
        ),
        pytest.param(
            SingleLinkParam(
                {"link_type": "PRESIGNED"},
                "http",
                _HTTP_PRESIGNED_LINK_QUERY_KEYS,
                TypeAdapter(ByteSize).validate_python("5GiB"),
            ),
            id="presigned_returns_single_presigned",
        ),
        pytest.param(
            SingleLinkParam(
                {"link_type": "S3"},
                "s3",
                [],
                TypeAdapter(ByteSize).validate_python("5TiB"),
            ),
            id="s3_returns_single_s3_link",
        ),
    ],
)
async def test_create_upload_file_with_no_file_size_query_returns_v1_structure(
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    simcore_file_id: SimcoreS3FileID,
    single_link_param: SingleLinkParam,
    sqlalchemy_async_engine: AsyncEngine,
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
        sqlalchemy_async_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=bool(single_link_param.expected_link_scheme == "s3"),
        expected_upload_expiration_date=True,
        expected_sha256_checksum=None,
    )
    # check that no s3 multipart upload was initiated
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        expected_upload_ids=None,
    )


@dataclass(frozen=True)
class MultiPartParam:
    link_type: LinkType
    file_size: ByteSize
    expected_response: int
    expected_num_links: int
    expected_chunk_size: ByteSize


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "test_param",
    [
        pytest.param(
            MultiPartParam(
                link_type=LinkType.PRESIGNED,
                file_size=TypeAdapter(ByteSize).validate_python("10MiB"),
                expected_response=status.HTTP_200_OK,
                expected_num_links=1,
                expected_chunk_size=TypeAdapter(ByteSize).validate_python("10MiB"),
            ),
            id="10MiB file,presigned",
        ),
        pytest.param(
            MultiPartParam(
                link_type=LinkType.PRESIGNED,
                file_size=TypeAdapter(ByteSize).validate_python("100MiB"),
                expected_response=status.HTTP_200_OK,
                expected_num_links=10,
                expected_chunk_size=TypeAdapter(ByteSize).validate_python("10MiB"),
            ),
            id="100MiB file,presigned",
        ),
        pytest.param(
            MultiPartParam(
                link_type=LinkType.PRESIGNED,
                file_size=TypeAdapter(ByteSize).validate_python("5TiB"),
                expected_response=status.HTTP_200_OK,
                expected_num_links=8739,
                expected_chunk_size=TypeAdapter(ByteSize).validate_python("600MiB"),
            ),
            id="5TiB file,presigned",
        ),
        pytest.param(
            MultiPartParam(
                link_type=LinkType.PRESIGNED,
                file_size=TypeAdapter(ByteSize).validate_python("9431773844"),
                expected_response=status.HTTP_200_OK,
                expected_num_links=900,
                expected_chunk_size=TypeAdapter(ByteSize).validate_python("10MiB"),
            ),
            id="9431773844B (8.8Gib) file,presigned",
        ),
        pytest.param(
            MultiPartParam(
                link_type=LinkType.S3,
                file_size=TypeAdapter(ByteSize).validate_python("255GiB"),
                expected_response=status.HTTP_200_OK,
                expected_num_links=1,
                expected_chunk_size=TypeAdapter(ByteSize).validate_python("255GiB"),
            ),
            id="5TiB file,s3",
        ),
    ],
)
async def test_create_upload_file_presigned_with_file_size_returns_multipart_links_if_bigger_than_99MiB(  # noqa: N802
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    simcore_file_id: SimcoreS3FileID,
    test_param: MultiPartParam,
    sqlalchemy_async_engine: AsyncEngine,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    cleanup_user_projects_file_metadata: None,
):
    # create upload file link
    received_file_upload = await create_upload_file_link_v2(
        simcore_file_id,
        link_type=test_param.link_type.value,
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
        sqlalchemy_async_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=expect_upload_id,
        expected_upload_expiration_date=True,
        expected_sha256_checksum=None,
    )

    # check that the s3 multipart upload was initiated properly
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        expected_upload_ids=([upload_id] if upload_id else None),
    )


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "link_type, file_size",
    [
        (LinkType.PRESIGNED, TypeAdapter(ByteSize).validate_python("1000Mib")),
        (LinkType.S3, TypeAdapter(ByteSize).validate_python("1000Mib")),
    ],
    ids=byte_size_ids,
)
async def test_delete_unuploaded_file_correctly_cleans_up_db_and_s3(
    sqlalchemy_async_engine: AsyncEngine,
    client: httpx.AsyncClient,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    with_versioning_enabled: None,
    simcore_file_id: SimcoreS3FileID,
    link_type: LinkType,
    file_size: ByteSize,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
):
    # create upload file link
    upload_link = await create_upload_file_link_v2(
        simcore_file_id, link_type=link_type.value, file_size=file_size
    )
    expect_upload_id = bool(file_size >= MULTIPART_UPLOADS_MIN_TOTAL_SIZE)
    # we shall have an entry in the db, waiting for upload
    upload_id = await assert_file_meta_data_in_db(
        sqlalchemy_async_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=expect_upload_id,
        expected_upload_expiration_date=True,
        expected_sha256_checksum=None,
    )

    # check that the s3 multipart upload was initiated properly
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        expected_upload_ids=([upload_id] if upload_id else None),
    )
    # delete/abort file upload
    abort_url = URL(f"{upload_link.links.abort_upload}").relative()
    response = await client.post(f"{abort_url}")
    assert_status(response, status.HTTP_204_NO_CONTENT, None)

    # the DB shall be cleaned up
    await assert_file_meta_data_in_db(
        sqlalchemy_async_engine,
        file_id=simcore_file_id,
        expected_entry_exists=False,
        expected_file_size=None,
        expected_upload_id=None,
        expected_upload_expiration_date=None,
        expected_sha256_checksum=None,
    )
    # the multipart upload shall be aborted
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        expected_upload_ids=None,
    )


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "link_type, file_size",
    [
        (LinkType.PRESIGNED, TypeAdapter(ByteSize).validate_python("10Mib")),
        (LinkType.PRESIGNED, TypeAdapter(ByteSize).validate_python("1000Mib")),
        (LinkType.S3, TypeAdapter(ByteSize).validate_python("10Mib")),
        (LinkType.S3, TypeAdapter(ByteSize).validate_python("1000Mib")),
    ],
    ids=byte_size_ids,
)
async def test_upload_same_file_uuid_aborts_previous_upload(
    sqlalchemy_async_engine: AsyncEngine,
    client: httpx.AsyncClient,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    simcore_file_id: SimcoreS3FileID,
    link_type: LinkType,
    file_size: ByteSize,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
):
    # create upload file link
    file_upload_link = await create_upload_file_link_v2(
        simcore_file_id, link_type=link_type.value, file_size=file_size
    )
    expect_upload_id = bool(
        file_size >= MULTIPART_UPLOADS_MIN_TOTAL_SIZE or link_type == LinkType.S3
    )
    # we shall have an entry in the db, waiting for upload
    upload_id = await assert_file_meta_data_in_db(
        sqlalchemy_async_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=expect_upload_id,
        expected_upload_expiration_date=True,
        expected_sha256_checksum=None,
    )

    # check that the s3 multipart upload was initiated properly
    await assert_multipart_uploads_in_progress(
        storage_s3_client,
        storage_s3_bucket,
        expected_upload_ids=([upload_id] if upload_id else None),
    )

    # now we create a new upload, in case it was a multipart,
    # we should abort the previous upload to prevent unwanted costs
    await asyncio.sleep(1)
    new_file_upload_link = await create_upload_file_link_v2(
        simcore_file_id, link_type=link_type.value, file_size=file_size
    )
    if link_type == LinkType.PRESIGNED:
        assert file_upload_link != new_file_upload_link
    else:
        assert file_upload_link == new_file_upload_link
    # we shall have an entry in the db, waiting for upload
    new_upload_id = await assert_file_meta_data_in_db(
        sqlalchemy_async_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=expect_upload_id,
        expected_upload_expiration_date=True,
        expected_sha256_checksum=None,
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
        expected_upload_ids=([new_upload_id] if new_upload_id else None),
    )


@pytest.fixture
def complex_file_name(faker: Faker) -> str:
    return f"subfolder_1/sub_folder 2/some file name with spaces and special characters  -_ü!öäàé+|}} {{3245_{faker.file_name()}"


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "file_size",
    [
        (TypeAdapter(ByteSize).validate_python("1Mib")),
        (TypeAdapter(ByteSize).validate_python("127Mib")),
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
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_upload_of_single_presigned_link_lazily_update_database_on_get(
    sqlalchemy_async_engine: AsyncEngine,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    client: httpx.AsyncClient,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    project_id: ProjectID,
    node_id: NodeID,
    faker: Faker,
    get_file_meta_data: Callable[..., Awaitable[FileMetaDataGet]],
    s3_client: S3Client,
):
    file_size = TypeAdapter(ByteSize).validate_python("127Mib")
    file_name = faker.file_name()
    # create a file
    file = create_file_of_size(file_size, file_name)
    simcore_file_id = create_simcore_file_id(project_id, node_id, file_name)
    # get an S3 upload link
    file_upload_link = await create_upload_file_link_v2(
        simcore_file_id, link_type="S3", file_size=file_size
    )
    assert file_upload_link
    # let's use the storage s3 internal client to upload
    with file.open("rb") as fp:
        response = await s3_client.put_object(
            Bucket=storage_s3_bucket, Key=simcore_file_id, Body=fp
        )
        assert "ETag" in response
        upload_e_tag = json.loads(response["ETag"])
    # check the file is now on S3
    s3_metadata = await storage_s3_client.get_object_metadata(
        bucket=storage_s3_bucket, object_key=simcore_file_id
    )
    assert s3_metadata.size == file_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag == upload_e_tag
    # check getting the file actually lazily updates the table and returns the expected values
    received_fmd: FileMetaDataGet = await get_file_meta_data(simcore_file_id)
    assert received_fmd.entity_tag == upload_e_tag


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_upload_real_file_with_s3_client(
    sqlalchemy_async_engine: AsyncEngine,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    client: httpx.AsyncClient,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    project_id: ProjectID,
    node_id: NodeID,
    faker: Faker,
    s3_client: S3Client,
    with_storage_celery_worker: CeleryTaskManager,
):
    file_size = TypeAdapter(ByteSize).validate_python("500Mib")
    file_name = faker.file_name()
    # create a file
    file = create_file_of_size(file_size, file_name)
    simcore_file_id = create_simcore_file_id(project_id, node_id, file_name)
    # get an S3 upload link
    file_upload_link = await create_upload_file_link_v2(
        simcore_file_id, link_type="S3", file_size=file_size
    )
    # let's use the storage s3 internal client to upload
    with file.open("rb") as fp:
        response = await s3_client.put_object(
            Bucket=storage_s3_bucket, Key=simcore_file_id, Body=fp
        )
        assert "ETag" in response
        upload_e_tag = json.loads(response["ETag"])
    # check the file is now on S3
    s3_metadata = await storage_s3_client.get_object_metadata(
        bucket=storage_s3_bucket, object_key=simcore_file_id
    )
    assert s3_metadata.size == file_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag == upload_e_tag

    # complete the upload
    complete_url = URL(f"{file_upload_link.links.complete_upload}").relative()
    with log_context(logging.INFO, f"completing upload of {file=}"):
        response = await client.post(f"{complete_url}", json={"parts": []})
        response.raise_for_status()
        file_upload_complete_response, error = assert_status(
            response, status.HTTP_202_ACCEPTED, FileUploadCompleteResponse
        )
        assert not error
        assert file_upload_complete_response
        state_url = URL(f"{file_upload_complete_response.links.state}").relative()
        completion_etag = None
        async for attempt in AsyncRetrying(
            reraise=True,
            wait=wait_fixed(1),
            stop=stop_after_delay(60),
            retry=retry_if_exception_type(ValueError),
        ):
            with (
                attempt,
                log_context(
                    logging.INFO,
                    f"waiting for upload completion {state_url=}, {attempt.retry_state.attempt_number}",
                ) as ctx,
            ):
                response = await client.post(f"{state_url}")
                response.raise_for_status()
                future, error = assert_status(
                    response, status.HTTP_200_OK, FileUploadCompleteFutureResponse
                )
                assert not error
                assert future
                if future.state != FileUploadCompleteState.OK:
                    msg = f"{future=}"
                    raise ValueError(msg)
                assert future.state == FileUploadCompleteState.OK
                assert future.e_tag is not None
                completion_etag = future.e_tag
                ctx.logger.info(
                    "%s",
                    f"--> done waiting, data is completely uploaded [{attempt.retry_state.retry_object.statistics}]",
                )

    # check the entry in db now has the correct file size, and the upload id is gone
    await assert_file_meta_data_in_db(
        sqlalchemy_async_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=file_size,
        expected_upload_id=False,
        expected_upload_expiration_date=False,
        expected_sha256_checksum=None,
    )
    # check the file is in S3 for real
    s3_metadata = await storage_s3_client.get_object_metadata(
        bucket=storage_s3_bucket, object_key=simcore_file_id
    )
    assert s3_metadata.size == file_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag == completion_etag


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "file_size",
    [
        TypeAdapter(ByteSize).validate_python("160Mib"),
        TypeAdapter(ByteSize).validate_python("1Mib"),
    ],
    ids=byte_size_ids,
)
async def test_upload_twice_and_fail_second_time_shall_keep_first_version(
    sqlalchemy_async_engine: AsyncEngine,
    client: httpx.AsyncClient,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    with_versioning_enabled: None,
    file_size: ByteSize,
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    faker: Faker,
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    user_id: UserID,
    location_id: LocationID,
):
    # 1. upload a valid file
    file_name = faker.file_name()
    _, uploaded_file_id = await upload_file(file_size, file_name)

    # 2. create an upload link for the second file
    upload_link = await create_upload_file_link_v2(
        uploaded_file_id, link_type="PRESIGNED", file_size=file_size
    )
    # we shall have an entry in the db, waiting for upload
    await assert_file_meta_data_in_db(
        sqlalchemy_async_engine,
        file_id=uploaded_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_id=bool(file_size >= MULTIPART_UPLOADS_MIN_TOTAL_SIZE),
        expected_upload_expiration_date=True,
        expected_sha256_checksum=None,
    )

    # 3. upload part of the file to simulate a network issue in the upload
    new_file = create_file_of_size(file_size, file_name)
    with pytest.raises(RuntimeError):
        async with httpx.AsyncClient() as session:
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
    abort_url = URL(f"{upload_link.links.abort_upload}").relative()
    response = await client.post(f"{abort_url}")
    assert_status(response, status.HTTP_204_NO_CONTENT, None)

    # we should have the original file still in now...
    await assert_file_meta_data_in_db(
        sqlalchemy_async_engine,
        file_id=uploaded_file_id,
        expected_entry_exists=True,
        expected_file_size=file_size,
        expected_upload_id=False,
        expected_upload_expiration_date=False,
        expected_sha256_checksum=None,
    )
    # check the file is in S3 for real
    s3_metadata = await storage_s3_client.get_object_metadata(
        bucket=storage_s3_bucket, object_key=uploaded_file_id
    )
    assert s3_metadata.size == file_size


@pytest.fixture
def file_size() -> ByteSize:
    return TypeAdapter(ByteSize).validate_python("1Mib")


async def _assert_file_downloaded(
    faker: Faker, tmp_path: Path, link: AnyUrl, uploaded_file: Path
):
    dest_file = tmp_path / faker.file_name()
    async with ClientSession() as session:
        response = await session.get(f"{link}")
        response.raise_for_status()
        with dest_file.open("wb") as fp:
            fp.write(await response.read())
    assert dest_file.exists()
    # compare files
    assert filecmp.cmp(uploaded_file, dest_file)


async def test_download_file_no_file_was_uploaded(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    project_id: ProjectID,
    node_id: NodeID,
    user_id: UserID,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    fake_datcore_tokens: tuple[str, str],
):
    missing_file = TypeAdapter(SimcoreS3FileID).validate_python(
        f"{project_id}/{node_id}/missing.file"
    )
    assert (
        await storage_s3_client.object_exists(
            bucket=storage_s3_bucket, object_key=missing_file
        )
        is False
    )
    download_url = url_from_operation_id(
        client,
        initialized_app,
        "download_file",
        location_id=f"{location_id}",
        file_id=missing_file,
    ).with_query(user_id=user_id)

    response = await client.get(f"{download_url}")
    data, error = assert_status(response, status.HTTP_404_NOT_FOUND, None)
    assert data is None
    assert len(error["errors"]) == 1
    assert missing_file in error["errors"][0]


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_download_file_1_to_1_with_file_meta_data(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    file_size: ByteSize,
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    location_id: LocationID,
    user_id: UserID,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    tmp_path: Path,
    faker: Faker,
):
    # 2. file_meta_data entry corresponds to a file
    # upload a single file as a file_meta_data entry and check link
    uploaded_file, uploaded_file_uuid = await upload_file(
        file_size, "meta_data_entry_is_file.file"
    )
    assert (
        await storage_s3_client.object_exists(
            bucket=storage_s3_bucket, object_key=uploaded_file_uuid
        )
        is True
    )

    download_url = url_from_operation_id(
        client,
        initialized_app,
        "download_file",
        location_id=f"{location_id}",
        file_id=uploaded_file_uuid,
    ).with_query(user_id=user_id)
    response = await client.get(f"{download_url}")
    data, error = assert_status(response, status.HTTP_200_OK, FileDownloadResponse)
    assert not error
    assert data
    await _assert_file_downloaded(
        faker, tmp_path, link=data.link, uploaded_file=uploaded_file
    )


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_download_file_from_inside_a_directory(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    file_size: ByteSize,
    location_id: LocationID,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    create_empty_directory: Callable[
        [str, ProjectID, NodeID], Awaitable[SimcoreS3FileID]
    ],
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    tmp_path: Path,
    faker: Faker,
):
    # 3. file_meta_data entry corresponds to a directory
    # upload a file inside a directory and check the download link

    directory_name = "a-test-dir"
    dir_path_in_s3 = await create_empty_directory(directory_name, project_id, node_id)

    file_name = "meta_data_entry_is_dir.file"
    file_to_upload_in_dir = create_file_of_size(file_size, file_name)

    s3_file_id = TypeAdapter(SimcoreS3FileID).validate_python(
        f"{dir_path_in_s3}/{file_name}"
    )
    await storage_s3_client.upload_file(
        bucket=storage_s3_bucket,
        file=file_to_upload_in_dir,
        object_key=s3_file_id,
        bytes_transfered_cb=None,
    )
    assert (
        await storage_s3_client.object_exists(
            bucket=storage_s3_bucket, object_key=s3_file_id
        )
        is True
    )

    # finally check the download link
    download_url = url_from_operation_id(
        client,
        initialized_app,
        "download_file",
        location_id=f"{location_id}",
        file_id=s3_file_id,
    ).with_query(user_id=user_id)
    response = await client.get(f"{download_url}")
    file_download, error = assert_status(
        response, status.HTTP_200_OK, FileDownloadResponse
    )
    assert not error
    assert file_download

    await _assert_file_downloaded(
        faker, tmp_path, link=file_download.link, uploaded_file=file_to_upload_in_dir
    )


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_download_file_the_file_is_missing_from_the_directory(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    create_empty_directory: Callable[
        [str, ProjectID, NodeID], Awaitable[SimcoreS3FileID]
    ],
):
    # file_meta_data entry corresponds to a directory but file is not present in directory

    directory_name = "a-second-test-dir"
    dir_path_in_s3 = await create_empty_directory(directory_name, project_id, node_id)

    missing_s3_file_id = TypeAdapter(SimcoreS3FileID).validate_python(
        f"{dir_path_in_s3}/missing_inside_dir.file"
    )
    download_url = url_from_operation_id(
        client,
        initialized_app,
        "download_file",
        location_id=f"{location_id}",
        file_id=missing_s3_file_id,
    ).with_query(user_id=user_id)

    response = await client.get(f"{download_url}")
    data, error = assert_status(response, status.HTTP_404_NOT_FOUND, None)
    assert data is None
    assert missing_s3_file_id in error["errors"][0]


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_download_file_access_rights(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    user_id: UserID,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    faker: Faker,
):
    # project_id does not exist
    missing_file = TypeAdapter(SimcoreS3FileID).validate_python(
        f"{faker.uuid4()}/{faker.uuid4()}/project_id_is_missing"
    )
    assert (
        await storage_s3_client.object_exists(
            bucket=storage_s3_bucket, object_key=missing_file
        )
        is False
    )
    download_url = url_from_operation_id(
        client,
        initialized_app,
        "download_file",
        location_id=f"{location_id}",
        file_id=missing_file,
    ).with_query(user_id=user_id)

    response = await client.get(f"{download_url}")
    data, error = assert_status(response, status.HTTP_403_FORBIDDEN, None)
    assert data is None
    assert "Insufficient access rights" in error["errors"][0]


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "file_size",
    [
        pytest.param(TypeAdapter(ByteSize).validate_python("1Mib")),
    ],
    ids=byte_size_ids,
)
async def test_delete_file(
    sqlalchemy_async_engine: AsyncEngine,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    file_size: ByteSize,
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    location_id: LocationID,
    user_id: UserID,
    faker: Faker,
):
    _, uploaded_file_uuid = await upload_file(file_size, faker.file_name())

    delete_url = url_from_operation_id(
        client,
        initialized_app,
        "delete_file",
        location_id=f"{location_id}",
        file_id=uploaded_file_uuid,
    ).with_query(user_id=user_id)
    response = await client.delete(f"{delete_url}")
    assert_status(response, status.HTTP_204_NO_CONTENT, None)

    # check the entry in db is removed
    await assert_file_meta_data_in_db(
        sqlalchemy_async_engine,
        file_id=uploaded_file_uuid,
        expected_entry_exists=False,
        expected_file_size=None,
        expected_upload_id=None,
        expected_upload_expiration_date=None,
        expected_sha256_checksum=None,
    )
    # check the file is gone from S3
    with pytest.raises(S3KeyNotFoundError):
        await storage_s3_client.get_object_metadata(
            bucket=storage_s3_bucket, object_key=uploaded_file_uuid
        )


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_copy_as_soft_link(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
):
    # missing simcore_file_id returns 404
    missing_file_uuid = create_simcore_file_id(project_id, node_id, faker.file_name())
    invalid_link_id = create_simcore_file_id(uuid4(), uuid4(), faker.file_name())
    url = url_from_operation_id(
        client,
        initialized_app,
        "copy_as_soft_link",
        file_id=missing_file_uuid,
    ).with_query(user_id=user_id)
    response = await client.post(
        f"{url}", json=jsonable_encoder(SoftCopyBody(link_id=invalid_link_id))
    )
    assert_status(response, status.HTTP_404_NOT_FOUND, None)

    # now let's try with whatever link id
    file, original_file_uuid = await upload_file(
        TypeAdapter(ByteSize).validate_python("10Mib"), faker.file_name()
    )
    url = url_from_operation_id(
        client,
        initialized_app,
        "copy_as_soft_link",
        file_id=original_file_uuid,
    ).with_query(user_id=user_id)

    link_id = TypeAdapter(SimcoreS3FileID).validate_python(
        f"api/{node_id}/{faker.file_name()}"
    )
    response = await client.post(
        f"{url}", json=jsonable_encoder(SoftCopyBody(link_id=link_id))
    )
    fmd, error = assert_status(response, status.HTTP_200_OK, FileMetaDataGet)
    assert not error
    assert fmd
    assert fmd.file_id == link_id


async def _list_files(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    location_id: LocationID,
    *,
    expand_dirs: bool,
) -> list[FileMetaDataGet]:
    get_url = url_from_operation_id(
        client,
        initialized_app,
        "list_files_metadata",
        location_id=f"{location_id}",
    ).with_query(user_id=user_id, expand_dirs=f"{expand_dirs}".lower())
    response = await client.get(f"{get_url}")
    fmds, error = assert_status(response, status.HTTP_200_OK, list[FileMetaDataGet])
    assert not error
    assert fmds is not None
    return fmds


async def _list_files_legacy(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    location_id: LocationID,
) -> list[FileMetaDataGet]:
    return await _list_files(
        initialized_app,
        client,
        user_id,
        location_id,
        expand_dirs=True,
    )


async def _list_files_and_directories(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    location_id: LocationID,
) -> list[FileMetaDataGet]:
    return await _list_files(
        initialized_app,
        client,
        user_id,
        location_id,
        expand_dirs=False,
    )


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize("link_type", LinkType)
@pytest.mark.parametrize(
    "file_size",
    [
        ByteSize(0),
        TypeAdapter(ByteSize).validate_python("0"),
        TypeAdapter(ByteSize).validate_python("1TB"),
    ],
)
async def test_is_directory_link_forces_link_type_and_size(
    project_id: ProjectID,
    node_id: NodeID,
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    user_id: UserID,
    link_type: LinkType,
    file_size: ByteSize,
):
    DIR_NAME = "some-dir"
    directory_file_id = create_simcore_file_id(project_id, node_id, DIR_NAME)
    directory_file_upload: FileUploadSchema = await create_upload_file_link_v2(
        directory_file_id,
        link_type=link_type.value,
        is_directory="true",
        file_size=file_size,
    )
    # only gets 1 link regardless of size
    assert len(directory_file_upload.urls) == 1

    files_and_directories: list[FileMetaDataGet] = await _list_files_and_directories(
        initialized_app, client, user_id, location_id
    )
    assert len(files_and_directories) == 1
    assert files_and_directories[0].is_directory is True
    # file size is 0 since nothing is uploaded
    assert files_and_directories[0].file_size == 0


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_ensure_expand_dirs_defaults_true(
    initialized_app: FastAPI,
    mocker: MockerFixture,
    client: httpx.AsyncClient,
    user_id: UserID,
    location_id: LocationID,
):
    mocked_object = mocker.patch(
        "simcore_service_storage.simcore_s3_dsm.SimcoreS3DataManager.list_files",
        autospec=True,
    )

    get_url = url_from_operation_id(
        client,
        initialized_app,
        "list_files_metadata",
        location_id=f"{location_id}",
    ).with_query(user_id=user_id)
    await client.get(f"{get_url}")

    assert len(mocked_object.call_args_list) == 1
    call_args_list = mocked_object.call_args_list[0]
    assert "expand_dirs" in call_args_list.kwargs
    assert call_args_list.kwargs["expand_dirs"] is True


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_upload_file_is_directory_and_remove_content(
    initialized_app: FastAPI,
    create_empty_directory: Callable[
        [str, ProjectID, NodeID], Awaitable[SimcoreS3FileID]
    ],
    populate_directory: Callable[
        [ByteSize, str, ProjectID, NodeID, int, int],
        Awaitable[tuple[NodeID, dict[SimcoreS3FileID, FileIDDict]]],
    ],
    delete_directory: Callable[..., Awaitable[None]],
    client: httpx.AsyncClient,
    location_id: LocationID,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
):
    FILE_SIZE_IN_DIR = TypeAdapter(ByteSize).validate_python("1Mib")
    DIR_NAME = "some-dir"
    SUBDIR_COUNT = 4
    FILE_COUNT = 20

    # DIRECTORY CREATION (is empty)

    directory_in_s3 = await create_empty_directory(DIR_NAME, project_id, node_id)

    files_and_directories: list[FileMetaDataGet] = await _list_files_and_directories(
        initialized_app, client, user_id, location_id
    )
    assert len(files_and_directories) == 1

    list_of_files: list[FileMetaDataGet] = await _list_files_legacy(
        initialized_app, client, user_id, location_id
    )
    assert len(list_of_files) == 0

    # DIRECTORY WITH CONTENT

    await populate_directory(
        FILE_SIZE_IN_DIR,
        DIR_NAME,
        project_id,
        node_id,
        SUBDIR_COUNT,
        FILE_COUNT,
    )

    files_and_directories: list[FileMetaDataGet] = await _list_files_and_directories(
        initialized_app, client, user_id, location_id
    )
    assert len(files_and_directories) == 1

    list_of_files: list[FileMetaDataGet] = await _list_files_legacy(
        initialized_app, client, user_id, location_id
    )
    assert len(list_of_files) == FILE_COUNT

    # DELETE NOT EXISTING

    delete_url = url_from_operation_id(
        client,
        initialized_app,
        "delete_file",
        location_id=f"{location_id}",
        file_id="/".join(list_of_files[0].file_id.split("/")[:2]) + "/does_not_exist",
    ).with_query(user_id=user_id)
    response = await client.delete(f"{delete_url}")
    _, error = assert_status(response, status.HTTP_204_NO_CONTENT, None)
    assert error is None

    list_of_files: list[FileMetaDataGet] = await _list_files_legacy(
        initialized_app, client, user_id, location_id
    )

    assert len(list_of_files) == FILE_COUNT

    # DELETE ONE FILE FROM THE DIRECTORY

    delete_url = url_from_operation_id(
        client,
        initialized_app,
        "delete_file",
        location_id=f"{location_id}",
        file_id=list_of_files[0].file_id,
    ).with_query(user_id=user_id)
    response = await client.delete(f"{delete_url}")
    _, error = assert_status(response, status.HTTP_204_NO_CONTENT, None)
    assert error is None

    list_of_files = await _list_files_legacy(
        initialized_app, client, user_id, location_id
    )

    assert len(list_of_files) == FILE_COUNT - 1

    # DIRECTORY REMOVAL

    await delete_directory(directory_in_s3)

    list_of_files = await _list_files_legacy(
        initialized_app, client, user_id, location_id
    )
    assert len(list_of_files) == 0

    files_and_directories = await _list_files_and_directories(
        initialized_app, client, user_id, location_id
    )
    assert len(files_and_directories) == 0


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize("files_count", [1002])
async def test_listing_more_than_1000_objects_in_bucket(
    create_directory_with_files: Callable[
        [str, ByteSize, int, int, ProjectID, NodeID],
        Awaitable[
            tuple[SimcoreS3FileID, tuple[NodeID, dict[SimcoreS3FileID, FileIDDict]]]
        ],
    ],
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    files_count: int,
):
    SUBDIR_COUNT = 1
    await create_directory_with_files(
        "random-directory",
        TypeAdapter(ByteSize).validate_python("1"),
        SUBDIR_COUNT,
        files_count,
        project_id,
        node_id,
    )
    list_of_files = await _list_files_legacy(
        initialized_app, client, user_id, location_id
    )
    # for now no more than 1000 objects will be returned
    assert len(list_of_files) == 1000


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize("uuid_filter", [True, False])
@pytest.mark.parametrize(
    "project_params",
    [
        ProjectWithFilesParams(
            num_nodes=1,
            allowed_file_sizes=(TypeAdapter(ByteSize).validate_python("1b"),),
            workspace_files_count=0,
        ),
    ],
    ids=str,
)
async def test_listing_with_project_id_filter(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    user_id: UserID,
    faker: Faker,
    random_project_with_files: Callable[
        [ProjectWithFilesParams],
        Awaitable[
            tuple[dict[str, Any], dict[NodeID, dict[SimcoreS3FileID, FileIDDict]]]
        ],
    ],
    uuid_filter: bool,
    project_params: ProjectWithFilesParams,
):
    src_project, src_projects_list = await random_project_with_files(project_params)
    _, _ = await random_project_with_files(project_params)
    assert len(src_projects_list.keys()) > 0
    node_id = next(iter(src_projects_list.keys()))
    project_files_in_db = set(src_projects_list[node_id])
    assert len(project_files_in_db) > 0
    project_id = src_project["uuid"]
    project_file_name = Path(choice(list(project_files_in_db))).name  # noqa: S311

    query = {
        "user_id": user_id,
        "project_id": f"{project_id}",
        "uuid_filter": project_file_name if uuid_filter else None,
    }

    url = url_from_operation_id(
        client, initialized_app, "list_files_metadata", location_id=f"{location_id}"
    ).with_query(**{k: v for k, v in query.items() if v is not None})
    response = await client.get(f"{url}")
    list_of_files, _ = assert_status(
        response, status.HTTP_200_OK, list[FileMetaDataGet]
    )
    assert list_of_files

    if uuid_filter:
        assert len(list_of_files) == 1
        assert project_file_name == list_of_files[0].file_name
    else:
        assert project_files_in_db == {file.file_uuid for file in list_of_files}
