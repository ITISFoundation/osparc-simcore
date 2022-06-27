# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import filecmp
import json
import urllib.parse
from pathlib import Path
from time import perf_counter
from typing import Awaitable, Callable, Optional
from uuid import uuid4

import pytest
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestClient
from aiopg.sa import Engine
from faker import Faker
from models_library.api_schemas_storage import FileMetaDataGet, LinkType, SoftCopyBody
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, ByteSize, parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_storage.exceptions import S3KeyNotFoundError
from simcore_service_storage.models import S3BucketName
from simcore_service_storage.s3_client import StorageS3Client
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from tests.helpers.file_utils import upload_file_part
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


@pytest.mark.parametrize(
    "url_query, expected_link_scheme, expected_link_query_keys, expected_chunk_size",
    [
        pytest.param(
            {},
            "http",
            _HTTP_PRESIGNED_LINK_QUERY_KEYS,
            int(parse_obj_as(ByteSize, "5GiB").to("b")),
            id="default_returns_single_presigned",
        ),
        pytest.param(
            {"link_type": "presigned"},
            "http",
            _HTTP_PRESIGNED_LINK_QUERY_KEYS,
            int(parse_obj_as(ByteSize, "5GiB").to("b")),
            id="presigned_returns_single_presigned",
        ),
        pytest.param(
            {"link_type": "s3"},
            "s3",
            [],
            int(parse_obj_as(ByteSize, "5TiB").to("b")),
            id="s3_returns_single_s3_link",
        ),
    ],
)
async def test_create_upload_file_default_returns_single_link(
    storage_s3_client,
    storage_s3_bucket: S3BucketName,
    simcore_file_id: SimcoreS3FileID,
    url_query: dict[str, str],
    expected_link_scheme: str,
    expected_link_query_keys: list[str],
    expected_chunk_size: int,
    aiopg_engine: Engine,
    create_upload_file_link: Callable[..., Awaitable[AnyUrl]],
    cleanup_user_projects_file_metadata: None,
):
    # create upload file link
    received_file_upload = await create_upload_file_link(simcore_file_id, **url_query)
    # check links, there should be only 1
    assert len(received_file_upload.urls) == 1
    assert received_file_upload.urls[0].scheme == expected_link_scheme
    assert received_file_upload.urls[0].path
    assert received_file_upload.urls[0].path.endswith(
        f"{urllib.parse.quote(simcore_file_id, safe='/')}"
    )
    # the chunk_size
    assert received_file_upload.chunk_size == expected_chunk_size
    if expected_link_query_keys:
        assert received_file_upload.urls[0].query
        query = {
            query_str.split("=")[0]: query_str.split("=")[1]
            for query_str in received_file_upload.urls[0].query.split("&")
        }
        for key in expected_link_query_keys:
            assert key in query
    else:
        assert not received_file_upload.urls[0].query

    # now check the entry in the database is correct, there should be only one
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_expiration_date=True,
    )


@pytest.mark.parametrize(
    "link_type, file_size",
    [
        (LinkType.PRESIGNED, parse_obj_as(ByteSize, "1000Mib")),
        (LinkType.S3, parse_obj_as(ByteSize, "1000Mib")),
    ],
)
async def test_delete_unuploaded_file_correctly_cleans_up_db_and_s3(
    aiopg_engine: Engine,
    client: TestClient,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    simcore_file_id: SimcoreS3FileID,
    link_type: LinkType,
    file_size: ByteSize,
    create_upload_file_link: Callable[..., Awaitable[AnyUrl]],
):
    assert client.app
    # create upload file link
    upload_link = await create_upload_file_link(
        simcore_file_id, link_type=link_type.value.lower(), file_size=file_size
    )

    # we shall have an entry in the db, waiting for upload
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_expiration_date=True,
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
        expected_upload_expiration_date=None,
    )


@pytest.mark.parametrize(
    "link_type, file_size",
    [
        (LinkType.PRESIGNED, parse_obj_as(ByteSize, "10Mib")),
        (LinkType.PRESIGNED, parse_obj_as(ByteSize, "1000Mib")),
        (LinkType.S3, parse_obj_as(ByteSize, "10Mib")),
        (LinkType.S3, parse_obj_as(ByteSize, "1000Mib")),
    ],
)
async def test_upload_same_file_uuid_aborts_previous_upload(
    aiopg_engine: Engine,
    client: TestClient,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    simcore_file_id: SimcoreS3FileID,
    link_type: LinkType,
    file_size: ByteSize,
    create_upload_file_link: Callable[..., Awaitable[AnyUrl]],
):
    assert client.app
    # create upload file link
    file_upload_link = await create_upload_file_link(
        simcore_file_id, link_type=link_type.value.lower(), file_size=file_size
    )
    # we shall have an entry in the db, waiting for upload
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_expiration_date=True,
    )

    # now we create a new upload
    # we should abort the previous upload to prevent unwanted costs
    new_file_upload_link = await create_upload_file_link(
        simcore_file_id, link_type=link_type.value.lower(), file_size=file_size
    )
    if link_type == LinkType.PRESIGNED:
        assert file_upload_link != new_file_upload_link
    else:
        assert file_upload_link == new_file_upload_link
    # we shall have an entry in the db, waiting for upload
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=simcore_file_id,
        expected_entry_exists=True,
        expected_file_size=-1,
        expected_upload_expiration_date=True,
    )


@pytest.mark.parametrize(
    "file_name",
    [
        "some file name with spaces and extension.txt",
        "some name with special characters -_ü!öäàé++3245",
    ],
)
@pytest.mark.parametrize(
    "file_size",
    [
        pytest.param(parse_obj_as(ByteSize, "1Mib"), id="7Mib"),
        pytest.param(parse_obj_as(ByteSize, "500Mib"), id="500Mib"),
        # pytest.param(parse_obj_as(ByteSize, "5Gib"), id="5Gib"),
        # pytest.param(parse_obj_as(ByteSize, "7Gib"), id="7Gib"),
    ],
)
async def test_upload_real_file(
    file_name: str,
    file_size: ByteSize,
    upload_file: Callable[[ByteSize, str], Awaitable[Path]],
):
    await upload_file(file_size, file_name)


async def test_upload_real_file_with_s3_client(
    aiopg_engine: Engine,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    client: TestClient,
    create_upload_file_link: Callable[..., Awaitable[AnyUrl]],
    create_file_of_size: Callable[[ByteSize, Optional[str]], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    project_id: ProjectID,
    node_id: NodeID,
    faker: Faker,
):
    assert client.app
    file_size = parse_obj_as(ByteSize, "500Mib")
    file_name = faker.file_name()
    # create a file
    file = create_file_of_size(file_size, file_name)
    simcore_file_id = create_simcore_file_id(project_id, node_id, file_name)
    # get an S3 upload link
    file_upload_link = await create_upload_file_link(
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
    "file_size", [parse_obj_as(ByteSize, "160Mib"), parse_obj_as(ByteSize, "1Mib")]
)
async def test_upload_twice_and_fail_second_time_shall_keep_first_version(
    aiopg_engine: Engine,
    client: TestClient,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    file_size: ByteSize,
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    faker: Faker,
    create_file_of_size: Callable[[ByteSize, Optional[str]], Path],
    create_upload_file_link: Callable[..., Awaitable[AnyUrl]],
):
    # 1. upload a valid file
    file_name = faker.file_name()
    _, uploaded_file_uuid = await upload_file(file_size, file_name)

    # 2. create an upload link for the second file
    upload_link = await create_upload_file_link(
        uploaded_file_uuid, link_type="presigned", file_size=file_size
    )
    # we shall have an entry in the db, waiting for upload
    await assert_file_meta_data_in_db(
        aiopg_engine,
        file_id=uploaded_file_uuid,
        expected_entry_exists=True,
        expected_file_size=-1,
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
        file_id=uploaded_file_uuid,
        expected_entry_exists=True,
        expected_file_size=file_size,
        expected_upload_expiration_date=False,
    )
    # check the file is in S3 for real
    s3_metadata = await storage_s3_client.get_file_metadata(
        storage_s3_bucket, uploaded_file_uuid
    )
    assert s3_metadata.size == file_size


@pytest.mark.parametrize(
    "file_size",
    [
        pytest.param(parse_obj_as(ByteSize, "1Mib"), id="7Mib"),
    ],
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
        pytest.param(parse_obj_as(ByteSize, "1Mib"), id="7Mib"),
    ],
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
