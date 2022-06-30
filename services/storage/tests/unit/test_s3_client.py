# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from contextlib import AsyncExitStack
from pathlib import Path
from random import choice
from typing import AsyncIterator, Awaitable, Callable, Final, Optional
from uuid import uuid4

import botocore.exceptions
import pytest
from aiohttp import ClientSession
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import SimcoreS3FileID
from pydantic import ByteSize, parse_obj_as
from pytest_simcore.helpers.utils_parametrizations import byte_size_ids
from simcore_service_storage.exceptions import S3BucketInvalidError, S3KeyNotFoundError
from simcore_service_storage.models import S3BucketName
from simcore_service_storage.s3_client import StorageS3Client
from simcore_service_storage.settings import Settings
from tests.helpers.file_utils import (
    parametrized_file_size,
    upload_file_to_presigned_link,
)

DEFAULT_EXPIRATION_SECS: Final[int] = 10


@pytest.fixture
def mock_config(mocked_s3_server_envs, monkeypatch: pytest.MonkeyPatch):
    # NOTE: override services/storage/tests/conftest.py::mock_config
    monkeypatch.setenv("STORAGE_POSTGRES", "null")


async def test_storage_storage_s3_client_creation(app_settings: Settings):
    assert app_settings.STORAGE_S3
    async with AsyncExitStack() as exit_stack:
        storage_s3_client = await StorageS3Client.create(
            exit_stack, app_settings.STORAGE_S3
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
            exit_stack, app_settings.STORAGE_S3
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

    await upload_file_to_presigned_link(file, presigned_url)

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


@pytest.fixture
def upload_file_single_presigned_link(
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    create_file_of_size: Callable[[ByteSize], Path],
) -> Callable[..., Awaitable[SimcoreS3FileID]]:
    async def _uploader(file_id: Optional[SimcoreS3FileID] = None) -> SimcoreS3FileID:
        file = create_file_of_size(parse_obj_as(ByteSize, "1Mib"))
        if not file_id:
            file_id = SimcoreS3FileID(file.name)
        presigned_url = await storage_s3_client.create_single_presigned_upload_link(
            storage_s3_bucket, file_id, expiration_secs=DEFAULT_EXPIRATION_SECS
        )
        assert presigned_url

        await upload_file_to_presigned_link(file, presigned_url)

        # check the object is complete
        s3_metadata = await storage_s3_client.get_file_metadata(
            storage_s3_bucket, file_id
        )
        assert s3_metadata.size == file.stat().st_size
        return file_id

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
    create_file_of_size: Callable[[ByteSize, Optional[str]], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
) -> Callable[[ByteSize], Awaitable[tuple[Path, SimcoreS3FileID]]]:
    async def _uploader(file_size: ByteSize) -> tuple[Path, SimcoreS3FileID]:
        file_name = faker.file_name()
        file = create_file_of_size(file_size, file_name)
        file_id = create_simcore_file_id(uuid4(), uuid4(), file_name)
        response = await storage_s3_client.upload_file(storage_s3_bucket, file, file_id)
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
    create_file_of_size: Callable[[ByteSize, Optional[str]], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
):
    file = create_file_of_size(ByteSize(10), None)
    file_id = create_simcore_file_id(uuid4(), uuid4(), file.name)
    with pytest.raises(S3BucketInvalidError):
        await storage_s3_client.upload_file(
            S3BucketName("pytestinvalidbucket"), file, file_id
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
    await storage_s3_client.copy_file(storage_s3_bucket, src_file_uuid, dst_file_uuid)

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
            S3BucketName("pytestinvalidbucket"), src_file_uuid, dst_file_uuid
        )
    with pytest.raises(S3KeyNotFoundError):
        await storage_s3_client.copy_file(
            storage_s3_bucket, SimcoreS3FileID("missing_file_uuid"), dst_file_uuid
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
