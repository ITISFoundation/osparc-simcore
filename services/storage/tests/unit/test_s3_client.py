# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


import asyncio
import json
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from random import choice
from typing import AsyncIterator, Awaitable, Callable, Final
from uuid import uuid4

import botocore.exceptions
import pytest
from aiohttp import ClientSession
from faker import Faker
from models_library.api_schemas_storage import UploadedPart
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import SimcoreS3FileID
from pydantic import ByteSize, parse_obj_as
from pytest_mock import MockFixture
from pytest_simcore.helpers.utils_parametrizations import byte_size_ids
from simcore_service_storage.exceptions import (
    S3AccessError,
    S3BucketInvalidError,
    S3KeyNotFoundError,
)
from simcore_service_storage.models import MultiPartUploadLinks, S3BucketName
from simcore_service_storage.s3_client import (
    NextContinuationToken,
    StorageS3Client,
    _list_objects_v2_paginated,
)
from simcore_service_storage.settings import Settings
from tests.helpers.file_utils import (
    parametrized_file_size,
    upload_file_to_presigned_link,
)
from types_aiobotocore_s3.type_defs import ObjectTypeDef

DEFAULT_EXPIRATION_SECS: Final[int] = 10


@pytest.fixture
def mock_config(mocked_s3_server_envs, monkeypatch: pytest.MonkeyPatch):
    # NOTE: override services/storage/tests/conftest.py::mock_config
    monkeypatch.setenv("STORAGE_POSTGRES", "null")


async def test_storage_storage_s3_client_creation(app_settings: Settings):
    assert app_settings.STORAGE_S3
    async with AsyncExitStack() as exit_stack:
        storage_s3_client = await StorageS3Client.create(
            exit_stack,
            app_settings.STORAGE_S3,
            app_settings.STORAGE_S3_CLIENT_MAX_TRANSFER_CONCURRENCY,
        )
        assert storage_s3_client
        response = await storage_s3_client.client.list_buckets()
        assert not response["Buckets"]
    with pytest.raises(botocore.exceptions.HTTPClientError):
        await storage_s3_client.client.list_buckets()


async def _clean_bucket_content(
    storage_s3_client: StorageS3Client, bucket: S3BucketName
):
    response = await storage_s3_client.client.list_objects_v2(Bucket=bucket)
    while response["KeyCount"] > 0:
        await storage_s3_client.client.delete_objects(
            Bucket=bucket,
            Delete={
                "Objects": [
                    {"Key": obj["Key"]} for obj in response["Contents"] if "Key" in obj
                ]
            },
        )
        response = await storage_s3_client.client.list_objects_v2(Bucket=bucket)


async def _remove_all_buckets(storage_s3_client: StorageS3Client):
    response = await storage_s3_client.client.list_buckets()
    bucket_names = [
        bucket["Name"] for bucket in response["Buckets"] if "Name" in bucket
    ]
    await asyncio.gather(
        *(
            _clean_bucket_content(storage_s3_client, S3BucketName(bucket))
            for bucket in bucket_names
        )
    )
    await asyncio.gather(
        *(
            storage_s3_client.client.delete_bucket(Bucket=bucket)
            for bucket in bucket_names
        )
    )


@pytest.fixture
async def storage_s3_client(
    app_settings: Settings,
) -> AsyncIterator[StorageS3Client]:
    assert app_settings.STORAGE_S3
    async with AsyncExitStack() as exit_stack:
        storage_s3_client = await StorageS3Client.create(
            exit_stack,
            app_settings.STORAGE_S3,
            app_settings.STORAGE_S3_CLIENT_MAX_TRANSFER_CONCURRENCY,
        )
        # check that no bucket is lying around
        assert storage_s3_client
        response = await storage_s3_client.client.list_buckets()
        assert not response[
            "Buckets"
        ], f"for testing puproses, there should be no bucket lying around! {response=}"
        yield storage_s3_client
        # cleanup
        await _remove_all_buckets(storage_s3_client)


async def test_create_bucket(storage_s3_client: StorageS3Client, faker: Faker):
    response = await storage_s3_client.client.list_buckets()
    assert not response["Buckets"]
    bucket = faker.pystr()
    await storage_s3_client.create_bucket(bucket)
    response = await storage_s3_client.client.list_buckets()
    assert response["Buckets"]
    assert len(response["Buckets"]) == 1
    assert "Name" in response["Buckets"][0]
    assert response["Buckets"][0]["Name"] == bucket
    # now we create the bucket again, it should silently work even if it exists already
    await storage_s3_client.create_bucket(bucket)
    response = await storage_s3_client.client.list_buckets()
    assert response["Buckets"]
    assert len(response["Buckets"]) == 1
    assert "Name" in response["Buckets"][0]
    assert response["Buckets"][0]["Name"] == bucket


@pytest.fixture
async def storage_s3_bucket(
    storage_s3_client: StorageS3Client, faker: Faker
) -> AsyncIterator[str]:
    response = await storage_s3_client.client.list_buckets()
    assert not response["Buckets"]
    bucket_name = faker.pystr()
    await storage_s3_client.create_bucket(bucket_name)
    response = await storage_s3_client.client.list_buckets()
    assert response["Buckets"]
    assert bucket_name in [
        bucket_struct.get("Name") for bucket_struct in response["Buckets"]
    ], f"failed creating {bucket_name}"

    yield bucket_name
    # cleanup the bucket
    await _clean_bucket_content(storage_s3_client, bucket_name)
    # remove bucket
    await storage_s3_client.client.delete_bucket(Bucket=bucket_name)
    response = await storage_s3_client.client.list_buckets()
    assert bucket_name not in [
        bucket_struct.get("Name") for bucket_struct in response["Buckets"]
    ], f"{bucket_name} is already in S3, please check why"


async def test_create_single_presigned_upload_link(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    create_file_of_size: Callable[[ByteSize], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
):
    file = create_file_of_size(parse_obj_as(ByteSize, "1Mib"))
    file_id = create_simcore_file_id(uuid4(), uuid4(), file.name)
    presigned_url = await storage_s3_client.create_single_presigned_upload_link(
        storage_s3_bucket, file_id, expiration_secs=DEFAULT_EXPIRATION_SECS
    )
    assert presigned_url

    # upload the file with a fake multipart upload links structure
    await upload_file_to_presigned_link(
        file,
        MultiPartUploadLinks(
            upload_id="fake",
            chunk_size=parse_obj_as(ByteSize, file.stat().st_size),
            urls=[presigned_url],
        ),
    )

    # check it is there
    s3_metadata = await storage_s3_client.get_file_metadata(storage_s3_bucket, file_id)
    assert s3_metadata.size == file.stat().st_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag


async def test_create_single_presigned_upload_link_invalid_raises(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    create_file_of_size: Callable[[ByteSize], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
):
    file = create_file_of_size(parse_obj_as(ByteSize, "1Mib"))
    file_id = create_simcore_file_id(uuid4(), uuid4(), file.name)
    with pytest.raises(S3BucketInvalidError):
        await storage_s3_client.create_single_presigned_upload_link(
            S3BucketName("pytestinvalidbucket"),
            file_id,
            expiration_secs=DEFAULT_EXPIRATION_SECS,
        )


@pytest.mark.parametrize(
    "file_size",
    [
        parametrized_file_size("10Mib"),
        parametrized_file_size("100Mib"),
        parametrized_file_size("1000Mib"),
    ],
    ids=byte_size_ids,
)
async def test_create_multipart_presigned_upload_link(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_multipart_presigned_link_without_completion: Callable[
        ..., Awaitable[tuple[SimcoreS3FileID, MultiPartUploadLinks, list[UploadedPart]]]
    ],
    file_size: ByteSize,
):
    (
        file_id,
        upload_links,
        uploaded_parts,
    ) = await upload_file_multipart_presigned_link_without_completion(file_size)

    # now complete it
    received_e_tag = await storage_s3_client.complete_multipart_upload(
        storage_s3_bucket, file_id, upload_links.upload_id, uploaded_parts
    )

    # check that the multipart upload is not listed anymore
    list_ongoing_uploads = await storage_s3_client.list_ongoing_multipart_uploads(
        storage_s3_bucket
    )
    assert list_ongoing_uploads == []

    # check the object is complete
    s3_metadata = await storage_s3_client.get_file_metadata(storage_s3_bucket, file_id)
    assert s3_metadata.size == file_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag == f"{json.loads(received_e_tag)}"


@pytest.mark.parametrize(
    "file_size",
    [
        parametrized_file_size("10Mib"),
    ],
    ids=byte_size_ids,
)
async def test_create_multipart_presigned_upload_link_invalid_raises(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_multipart_presigned_link_without_completion: Callable[
        ..., Awaitable[tuple[SimcoreS3FileID, MultiPartUploadLinks, list[UploadedPart]]]
    ],
    file_size: ByteSize,
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
):
    (
        file_id,
        upload_links,
        uploaded_parts,
    ) = await upload_file_multipart_presigned_link_without_completion(file_size)

    with pytest.raises(S3BucketInvalidError):
        await storage_s3_client.complete_multipart_upload(
            S3BucketName("pytestinvalidbucket"),
            file_id,
            upload_links.upload_id,
            uploaded_parts,
        )

    wrong_file_id = create_simcore_file_id(uuid4(), uuid4(), faker.file_name())
    # with pytest.raises(S3KeyNotFoundError):
    # NOTE: this does not raise... and it returns the file_id of the original file...
    await storage_s3_client.complete_multipart_upload(
        storage_s3_bucket, wrong_file_id, upload_links.upload_id, uploaded_parts
    )
    # call it again triggers
    with pytest.raises(S3AccessError):
        await storage_s3_client.complete_multipart_upload(
            storage_s3_bucket, wrong_file_id, upload_links.upload_id, uploaded_parts
        )


@pytest.mark.parametrize(
    "file_size", [parametrized_file_size("100Mib")], ids=byte_size_ids
)
async def test_abort_multipart_upload(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_multipart_presigned_link_without_completion: Callable[
        ..., Awaitable[tuple[SimcoreS3FileID, MultiPartUploadLinks, list[UploadedPart]]]
    ],
    file_size: ByteSize,
):
    (
        file_id,
        upload_links,
        _,
    ) = await upload_file_multipart_presigned_link_without_completion(file_size)

    # now abort it
    await storage_s3_client.abort_multipart_upload(
        storage_s3_bucket, file_id, upload_links.upload_id
    )

    # now check that the listing is empty
    ongoing_multipart_uploads = await storage_s3_client.list_ongoing_multipart_uploads(
        storage_s3_bucket
    )
    assert ongoing_multipart_uploads == []

    # check it is not available
    with pytest.raises(S3KeyNotFoundError):
        await storage_s3_client.get_file_metadata(storage_s3_bucket, file_id)


@pytest.mark.parametrize(
    "file_size", [parametrized_file_size("100Mib")], ids=byte_size_ids
)
async def test_multiple_completion_of_multipart_upload(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_multipart_presigned_link_without_completion: Callable[
        ..., Awaitable[tuple[SimcoreS3FileID, MultiPartUploadLinks, list[UploadedPart]]]
    ],
    file_size: ByteSize,
):
    (
        file_id,
        upload_links,
        uploaded_parts,
    ) = await upload_file_multipart_presigned_link_without_completion(file_size)

    # first completion
    await storage_s3_client.complete_multipart_upload(
        storage_s3_bucket, file_id, upload_links.upload_id, uploaded_parts
    )

    with pytest.raises(S3AccessError):
        await storage_s3_client.complete_multipart_upload(
            storage_s3_bucket, file_id, upload_links.upload_id, uploaded_parts
        )


@pytest.mark.parametrize("file_size", [parametrized_file_size("1Gib")])
async def test_break_completion_of_multipart_upload(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_multipart_presigned_link_without_completion: Callable[
        ..., Awaitable[tuple[SimcoreS3FileID, MultiPartUploadLinks, list[UploadedPart]]]
    ],
    file_size: ByteSize,
):
    (
        file_id,
        upload_links,
        uploaded_parts,
    ) = await upload_file_multipart_presigned_link_without_completion(file_size)
    # let's break the completion very quickly task and see what happens
    VERY_SHORT_TIMEOUT = 0.2
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            storage_s3_client.complete_multipart_upload(
                storage_s3_bucket, file_id, upload_links.upload_id, uploaded_parts
            ),
            timeout=VERY_SHORT_TIMEOUT,
        )
    # check we have the multipart upload initialized and listed
    ongoing_multipart_uploads = await storage_s3_client.list_ongoing_multipart_uploads(
        storage_s3_bucket
    )
    assert ongoing_multipart_uploads
    assert len(ongoing_multipart_uploads) == 1
    ongoing_upload_id, ongoing_file_id = ongoing_multipart_uploads[0]
    assert ongoing_upload_id == upload_links.upload_id
    assert ongoing_file_id == file_id

    # now wait
    await asyncio.sleep(10)

    # check that the completion of the update completed...
    assert (
        await storage_s3_client.list_ongoing_multipart_uploads(storage_s3_bucket) == []
    )

    # check the object is complete
    s3_metadata = await storage_s3_client.get_file_metadata(storage_s3_bucket, file_id)
    assert s3_metadata.size == file_size
    assert s3_metadata.last_modified
    assert s3_metadata.e_tag


@pytest.fixture
def upload_file_single_presigned_link(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    create_file_of_size: Callable[[ByteSize], Path],
) -> Callable[..., Awaitable[SimcoreS3FileID]]:
    async def _uploader(file_id: SimcoreS3FileID | None = None) -> SimcoreS3FileID:
        file = create_file_of_size(parse_obj_as(ByteSize, "1Mib"))
        if not file_id:
            file_id = SimcoreS3FileID(file.name)
        presigned_url = await storage_s3_client.create_single_presigned_upload_link(
            storage_s3_bucket, file_id, expiration_secs=DEFAULT_EXPIRATION_SECS
        )
        assert presigned_url

        # upload the file with a fake multipart upload links structure
        await upload_file_to_presigned_link(
            file,
            MultiPartUploadLinks(
                upload_id="fake",
                chunk_size=parse_obj_as(ByteSize, file.stat().st_size),
                urls=[presigned_url],
            ),
        )

        # check the object is complete
        s3_metadata = await storage_s3_client.get_file_metadata(
            storage_s3_bucket, file_id
        )
        assert s3_metadata.size == file.stat().st_size
        return file_id

    return _uploader


@pytest.fixture
def upload_file_multipart_presigned_link_without_completion(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    create_file_of_size: Callable[[ByteSize], Path],
) -> Callable[
    ..., Awaitable[tuple[SimcoreS3FileID, MultiPartUploadLinks, list[UploadedPart]]]
]:
    async def _uploader(
        file_size: ByteSize,
        file_id: SimcoreS3FileID | None = None,
    ) -> tuple[SimcoreS3FileID, MultiPartUploadLinks, list[UploadedPart]]:
        file = create_file_of_size(file_size)
        if not file_id:
            file_id = SimcoreS3FileID(file.name)
        upload_links = await storage_s3_client.create_multipart_upload_links(
            storage_s3_bucket,
            file_id,
            ByteSize(file.stat().st_size),
            expiration_secs=DEFAULT_EXPIRATION_SECS,
        )
        assert upload_links

        # check there is no file yet
        with pytest.raises(S3KeyNotFoundError):
            await storage_s3_client.get_file_metadata(storage_s3_bucket, file_id)

        # check we have the multipart upload initialized and listed
        ongoing_multipart_uploads = (
            await storage_s3_client.list_ongoing_multipart_uploads(storage_s3_bucket)
        )
        assert ongoing_multipart_uploads
        assert len(ongoing_multipart_uploads) == 1
        ongoing_upload_id, ongoing_file_id = ongoing_multipart_uploads[0]
        assert ongoing_upload_id == upload_links.upload_id
        assert ongoing_file_id == file_id

        # upload the file
        uploaded_parts: list[UploadedPart] = await upload_file_to_presigned_link(
            file,
            upload_links,
        )
        assert len(uploaded_parts) == len(upload_links.urls)

        # check there is no file yet
        with pytest.raises(S3KeyNotFoundError):
            await storage_s3_client.get_file_metadata(storage_s3_bucket, file_id)

        # check we have the multipart upload initialized and listed
        ongoing_multipart_uploads = (
            await storage_s3_client.list_ongoing_multipart_uploads(storage_s3_bucket)
        )
        assert ongoing_multipart_uploads
        assert len(ongoing_multipart_uploads) == 1
        ongoing_upload_id, ongoing_file_id = ongoing_multipart_uploads[0]
        assert ongoing_upload_id == upload_links.upload_id
        assert ongoing_file_id == file_id

        return (
            file_id,
            upload_links,
            uploaded_parts,
        )

    return _uploader


async def test_delete_file(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_single_presigned_link: Callable[..., Awaitable[SimcoreS3FileID]],
):
    file_id = await upload_file_single_presigned_link()

    # delete the file
    await storage_s3_client.delete_file(storage_s3_bucket, file_id)

    # check it is not available
    with pytest.raises(S3KeyNotFoundError):
        await storage_s3_client.get_file_metadata(storage_s3_bucket, file_id)


async def test_delete_file_invalid_raises(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
):
    file_id = create_simcore_file_id(uuid4(), uuid4(), faker.file_name())
    with pytest.raises(S3BucketInvalidError):
        await storage_s3_client.delete_file(
            S3BucketName("pytestinvalidbucket"), file_id
        )

    # this does not raise
    await storage_s3_client.delete_file(storage_s3_bucket, file_id)


async def test_delete_files_in_project_node(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_single_presigned_link: Callable[..., Awaitable[SimcoreS3FileID]],
    faker: Faker,
):
    # we upload files in these paths
    project_1 = uuid4()
    project_2 = uuid4()
    node_1 = uuid4()
    node_2 = uuid4()
    node_3 = uuid4()
    upload_paths = (
        "",
        f"{project_1}/",
        f"{project_1}/{node_1}/",
        f"{project_1}/{node_2}/",
        f"{project_1}/{node_2}/",
        f"{project_1}/{node_3}/",
        f"{project_1}/{node_3}/",
        f"{project_1}/{node_3}/",
        f"{project_2}/",
        f"{project_2}/{node_1}/",
        f"{project_2}/{node_2}/",
        f"{project_2}/{node_2}/",
        f"{project_2}/{node_2}/",
        f"{project_2}/{node_2}/",
        f"{project_2}/{node_3}/",
        f"{project_2}/{node_3}/states/",
        f"{project_2}/{node_3}/some_folder_of_sort/",
    )

    uploaded_file_ids = await asyncio.gather(
        *(
            upload_file_single_presigned_link(file_id=f"{path}{faker.file_name()}")
            for path in upload_paths
        )
    )
    assert len(uploaded_file_ids) == len(upload_paths)

    async def _assert_deleted(*, deleted_ids: tuple[str, ...]):
        for file_id in uploaded_file_ids:
            if file_id.startswith(deleted_ids):
                with pytest.raises(S3KeyNotFoundError):
                    await storage_s3_client.get_file_metadata(
                        storage_s3_bucket, file_id
                    )
            else:
                s3_metadata = await storage_s3_client.get_file_metadata(
                    storage_s3_bucket, file_id
                )
                assert s3_metadata.e_tag

    # now let's delete some files and check they are correctly deleted
    await storage_s3_client.delete_files_in_project_node(
        storage_s3_bucket, project_1, node_3
    )
    await _assert_deleted(deleted_ids=(f"{project_1}/{node_3}",))

    # delete some stuff in project 2
    await storage_s3_client.delete_files_in_project_node(
        storage_s3_bucket, project_2, node_3
    )
    await _assert_deleted(
        deleted_ids=(
            f"{project_1}/{node_3}",
            f"{project_2}/{node_3}",
        )
    )

    # completely delete project 2
    await storage_s3_client.delete_files_in_project_node(
        storage_s3_bucket, project_2, None
    )
    await _assert_deleted(
        deleted_ids=(
            f"{project_1}/{node_3}",
            f"{project_2}",
        )
    )


async def test_delete_files_in_project_node_invalid_raises(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_single_presigned_link: Callable[..., Awaitable[SimcoreS3FileID]],
    faker: Faker,
):
    with pytest.raises(S3BucketInvalidError):
        await storage_s3_client.delete_files_in_project_node(
            S3BucketName("pytestinvalidbucket"), uuid4(), uuid4()
        )
    #  this should not raise
    await storage_s3_client.delete_files_in_project_node(
        storage_s3_bucket, uuid4(), uuid4()
    )


async def test_create_single_presigned_download_link(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_single_presigned_link: Callable[..., Awaitable[SimcoreS3FileID]],
    tmp_path: Path,
    faker: Faker,
):
    file_id = await upload_file_single_presigned_link()

    presigned_url = await storage_s3_client.create_single_presigned_download_link(
        storage_s3_bucket, file_id, expiration_secs=DEFAULT_EXPIRATION_SECS
    )

    assert presigned_url

    dest_file = tmp_path / faker.file_name()
    # download the file
    async with ClientSession() as session:
        response = await session.get(presigned_url)
        response.raise_for_status()
        with dest_file.open("wb") as fp:
            fp.write(await response.read())
    assert dest_file.exists()

    s3_metadata = await storage_s3_client.get_file_metadata(storage_s3_bucket, file_id)
    assert s3_metadata.e_tag
    assert s3_metadata.last_modified
    assert dest_file.stat().st_size == s3_metadata.size


async def test_create_single_presigned_download_link_invalid_raises(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_single_presigned_link: Callable[..., Awaitable[SimcoreS3FileID]],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
):
    file_id = await upload_file_single_presigned_link()

    with pytest.raises(S3BucketInvalidError):
        await storage_s3_client.create_single_presigned_download_link(
            S3BucketName("invalidpytestbucket"),
            file_id,
            expiration_secs=DEFAULT_EXPIRATION_SECS,
        )
    wrong_file_id = create_simcore_file_id(uuid4(), uuid4(), faker.file_name())
    with pytest.raises(S3KeyNotFoundError):
        await storage_s3_client.create_single_presigned_download_link(
            storage_s3_bucket, wrong_file_id, expiration_secs=DEFAULT_EXPIRATION_SECS
        )


@pytest.fixture
async def upload_file_with_aioboto3_managed_transfer(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    faker: Faker,
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
) -> Callable[[ByteSize], Awaitable[tuple[Path, SimcoreS3FileID]]]:
    async def _uploader(file_size: ByteSize) -> tuple[Path, SimcoreS3FileID]:
        file_name = faker.file_name()
        file = create_file_of_size(file_size, file_name)
        file_id = create_simcore_file_id(uuid4(), uuid4(), file_name)
        response = await storage_s3_client.upload_file(
            storage_s3_bucket, file, file_id, bytes_transfered_cb=None
        )
        # there is no response from aioboto3...
        assert not response
        # check the object is uploaded
        response = await storage_s3_client.client.list_objects_v2(
            Bucket=storage_s3_bucket
        )
        assert "Contents" in response
        list_objects = response["Contents"]
        assert len(list_objects) >= 1
        # find our object now
        for s3_obj in list_objects:
            if s3_obj.get("Key") == file_id:
                # found it!
                assert "ETag" in s3_obj
                assert "Key" in s3_obj
                assert s3_obj["Key"] == file_id
                assert "Size" in s3_obj
                assert s3_obj["Size"] == file.stat().st_size
                return file, file_id
        assert False, "Object was not properly uploaded!"

    return _uploader


@pytest.mark.parametrize(
    "file_size",
    [parametrized_file_size("500Mib")],
    ids=byte_size_ids,
)
async def test_upload_file(
    file_size: ByteSize,
    upload_file_with_aioboto3_managed_transfer: Callable[
        [ByteSize], Awaitable[tuple[Path, SimcoreS3FileID]]
    ],
):
    await upload_file_with_aioboto3_managed_transfer(file_size)


async def test_upload_file_invalid_raises(
    storage_s3_client: StorageS3Client,
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
):
    file = create_file_of_size(ByteSize(10), None)
    file_id = create_simcore_file_id(uuid4(), uuid4(), file.name)
    with pytest.raises(S3BucketInvalidError):
        await storage_s3_client.upload_file(
            S3BucketName("pytestinvalidbucket"), file, file_id, bytes_transfered_cb=None
        )


@pytest.mark.parametrize(
    "file_size",
    [parametrized_file_size("500Mib")],
    ids=byte_size_ids,
)
async def test_copy_file(
    file_size: ByteSize,
    upload_file_with_aioboto3_managed_transfer: Callable[
        [ByteSize], Awaitable[tuple[Path, SimcoreS3FileID]]
    ],
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
):
    src_file, src_file_uuid = await upload_file_with_aioboto3_managed_transfer(
        file_size
    )
    dst_file_name = faker.file_name()
    dst_file_uuid = create_simcore_file_id(uuid4(), uuid4(), dst_file_name)
    await storage_s3_client.copy_file(
        storage_s3_bucket, src_file_uuid, dst_file_uuid, bytes_transfered_cb=None
    )

    # check the object is uploaded
    response = await storage_s3_client.client.list_objects_v2(Bucket=storage_s3_bucket)
    assert "Contents" in response
    list_objects = response["Contents"]
    assert len(list_objects) == 2

    list_file_uuids = [src_file_uuid, dst_file_uuid]
    for s3_obj in list_objects:
        assert "ETag" in s3_obj
        assert "Key" in s3_obj
        assert s3_obj["Key"] in list_file_uuids
        list_file_uuids.pop(list_file_uuids.index(s3_obj["Key"]))
        assert "Size" in s3_obj
        assert s3_obj["Size"] == src_file.stat().st_size


async def test_copy_file_invalid_raises(
    upload_file_with_aioboto3_managed_transfer: Callable[
        [ByteSize], Awaitable[tuple[Path, SimcoreS3FileID]]
    ],
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
):
    _, src_file_uuid = await upload_file_with_aioboto3_managed_transfer(ByteSize(1024))
    dst_file_name = faker.file_name()
    dst_file_uuid = create_simcore_file_id(uuid4(), uuid4(), dst_file_name)
    with pytest.raises(S3BucketInvalidError):
        await storage_s3_client.copy_file(
            S3BucketName("pytestinvalidbucket"),
            src_file_uuid,
            dst_file_uuid,
            bytes_transfered_cb=None,
        )
    with pytest.raises(S3KeyNotFoundError):
        await storage_s3_client.copy_file(
            storage_s3_bucket,
            SimcoreS3FileID("missing_file_uuid"),
            dst_file_uuid,
            bytes_transfered_cb=None,
        )


async def test_list_files(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_with_aioboto3_managed_transfer: Callable[
        [ByteSize], Awaitable[tuple[Path, SimcoreS3FileID]]
    ],
):
    list_files = await storage_s3_client.list_files(storage_s3_bucket, prefix="")
    assert list_files == []

    NUM_FILES = 12
    FILE_SIZE = parse_obj_as(ByteSize, "11Mib")
    uploaded_files: list[tuple[Path, SimcoreS3FileID]] = []
    for _ in range(NUM_FILES):
        uploaded_files.append(
            await upload_file_with_aioboto3_managed_transfer(FILE_SIZE)
        )

    list_files = await storage_s3_client.list_files(storage_s3_bucket, prefix="")
    assert len(list_files) == NUM_FILES
    # test with prefix
    file, file_id = choice(uploaded_files)
    list_files = await storage_s3_client.list_files(storage_s3_bucket, prefix=file_id)
    assert len(list_files) == 1
    assert list_files[0].file_id == file_id
    assert list_files[0].size == file.stat().st_size


async def test_list_files_invalid_bucket_raises(
    storage_s3_client: StorageS3Client,
):
    with pytest.raises(S3BucketInvalidError):
        await storage_s3_client.list_files(
            S3BucketName("pytestinvalidbucket"), prefix=""
        )


@dataclass
class PaginationCase:
    total_files: int
    items_per_page: int
    expected_queried_pages: int
    mock_upper_bound: int


@pytest.mark.parametrize(
    "pagination_case",
    [
        pytest.param(
            PaginationCase(
                total_files=10,
                items_per_page=2,
                expected_queried_pages=5,
                mock_upper_bound=1000,
            ),
            id="normal_query",
        ),
        pytest.param(
            PaginationCase(
                total_files=10,
                items_per_page=10,
                expected_queried_pages=5,
                mock_upper_bound=2,
            ),
            id="page_too_big",
        ),
    ],
)
async def test_list_objects_v2_paginated(
    mocker: MockFixture,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_with_aioboto3_managed_transfer: Callable[
        [ByteSize], Awaitable[tuple[Path, SimcoreS3FileID]]
    ],
    pagination_case: PaginationCase,
):
    mocker.patch(
        "simcore_service_storage.s3_client._PAGE_MAX_ITEMS_UPPER_BOUND",
        pagination_case.mock_upper_bound,
    )

    FILE_SIZE: ByteSize = parse_obj_as(ByteSize, "1")

    # create some files
    await asyncio.gather(
        *[
            upload_file_with_aioboto3_managed_transfer(FILE_SIZE)
            for _ in range(pagination_case.total_files)
        ]
    )

    # fetch all items using pagination
    listing_requests: list[ObjectTypeDef] = []
    next_continuation_token: NextContinuationToken | None = None
    pages_queried: int = 0
    while True:
        pages_queried += 1
        page_items, next_continuation_token = await _list_objects_v2_paginated(
            client=storage_s3_client.client,
            bucket=storage_s3_bucket,
            prefix="",  # all items
            max_total_items=pagination_case.items_per_page,
            next_continuation_token=next_continuation_token,
        )
        listing_requests.extend(page_items)

        if next_continuation_token is None:
            break

    assert len(listing_requests) == pagination_case.total_files
    assert pages_queried == pagination_case.expected_queried_pages


async def test_file_exists(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_with_aioboto3_managed_transfer: Callable[
        [ByteSize], Awaitable[tuple[Path, SimcoreS3FileID]]
    ],
):
    FILE_SIZE: ByteSize = parse_obj_as(ByteSize, "1")

    _, simcore_s3_file_id = await upload_file_with_aioboto3_managed_transfer(FILE_SIZE)
    assert (
        await storage_s3_client.file_exists(
            bucket=storage_s3_bucket, s3_object=simcore_s3_file_id
        )
        is True
    )

    assert (
        await storage_s3_client.file_exists(
            bucket=storage_s3_bucket, s3_object="fake-missing-object"
        )
        is False
    )
