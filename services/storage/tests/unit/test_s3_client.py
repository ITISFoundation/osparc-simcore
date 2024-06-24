# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from random import choice
from typing import Final
from uuid import uuid4

import botocore.exceptions
import pytest
from aws_library.s3.errors import S3BucketInvalidError, S3KeyNotFoundError
from faker import Faker
from models_library.projects_nodes_io import SimcoreS3FileID
from pydantic import ByteSize, parse_obj_as
from pytest_mock import MockFixture
from simcore_service_storage.models import S3BucketName
from simcore_service_storage.s3_client import StorageS3Client
from simcore_service_storage.settings import Settings
from types_aiobotocore_s3.type_defs import ObjectTypeDef

from tests.helpers.file_utils import parametrized_file_size

DEFAULT_EXPIRATION_SECS: Final[int] = 10

pytest_simcore_core_services_selection = ["postgres"]


async def test_storage_storage_s3_client_creation(
    app_settings: Settings,
):
    assert app_settings.STORAGE_S3
    storage_s3_client = await StorageS3Client.create(
        app_settings.STORAGE_S3,
        app_settings.STORAGE_S3_CLIENT_MAX_TRANSFER_CONCURRENCY,
    )
    assert storage_s3_client
    response = await storage_s3_client._client.list_buckets()
    assert not response["Buckets"]

    await storage_s3_client.close()
    with pytest.raises(botocore.exceptions.HTTPClientError):
        await storage_s3_client._client.list_buckets()


@pytest.fixture
async def storage_s3_client(
    app_settings: Settings,
) -> StorageS3Client:
    assert app_settings.STORAGE_S3
    storage_s3_client = await StorageS3Client.create(
        app_settings.STORAGE_S3,
        app_settings.STORAGE_S3_CLIENT_MAX_TRANSFER_CONCURRENCY,
    )
    # check that no bucket is lying around
    assert storage_s3_client
    response = await storage_s3_client._client.list_buckets()
    assert not response[
        "Buckets"
    ], f"for testing puproses, there should be no bucket lying around! {response=}"
    return storage_s3_client


@pytest.fixture
async def storage_s3_bucket(storage_s3_client: StorageS3Client, faker: Faker) -> str:
    response = await storage_s3_client._client.list_buckets()
    assert not response["Buckets"]
    bucket_name = parse_obj_as(S3BucketName, faker.pystr().replace("_", "-"))
    await storage_s3_client.create_bucket(bucket=bucket_name, region="us-east-1")
    response = await storage_s3_client._client.list_buckets()
    assert response["Buckets"]
    assert bucket_name in [
        bucket_struct.get("Name") for bucket_struct in response["Buckets"]
    ], f"failed creating {bucket_name}"

    return bucket_name


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
                        bucket=storage_s3_bucket, object_key=file_id
                    )
            else:
                s3_metadata = await storage_s3_client.get_file_metadata(
                    bucket=storage_s3_bucket, object_key=file_id
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

    # check with limits
    list_files = await storage_s3_client.list_files(
        storage_s3_bucket, prefix="", max_files_to_list=NUM_FILES - 2
    )
    assert len(list_files) == NUM_FILES - 2

    # test with prefix
    file, file_id = choice(uploaded_files)
    list_files = await storage_s3_client.list_files(storage_s3_bucket, prefix=file_id)
    assert len(list_files) == 1
    assert list_files[0].object_key == file_id
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
    mock_upper_bound: int


@pytest.mark.parametrize(
    "pagination_case",
    [
        pytest.param(
            PaginationCase(
                total_files=10,
                items_per_page=2,
                mock_upper_bound=1000,
            ),
            id="normal_query",
        ),
        pytest.param(
            PaginationCase(
                total_files=10,
                items_per_page=10,
                mock_upper_bound=2,
            ),
            id="page_too_big",
        ),
        pytest.param(
            PaginationCase(
                total_files=100,
                items_per_page=2,
                mock_upper_bound=2,
            ),
            id="regression_more_files_than_limit",
        ),
    ],
)
async def test_list_objects_v2_paginated_and_list_all_objects_gen(
    mocker: MockFixture,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    upload_file_with_aioboto3_managed_transfer: Callable[
        [ByteSize], Awaitable[tuple[Path, SimcoreS3FileID]]
    ],
    pagination_case: PaginationCase,
):
    mocker.patch(
        "simcore_service_storage.s3_client._MAX_ITEMS_PER_PAGE",
        pagination_case.mock_upper_bound,
    )

    FILE_SIZE: ByteSize = parse_obj_as(ByteSize, "1")

    # create some files
    created_files_data: list[tuple[Path, str]] = await asyncio.gather(
        *[
            upload_file_with_aioboto3_managed_transfer(FILE_SIZE)
            for _ in range(pagination_case.total_files)
        ]
    )

    # fetch all items using pagination
    listing_requests: list[ObjectTypeDef] = []

    async for page_items in _list_objects_v2_paginated_gen(
        client=storage_s3_client._client,
        bucket=storage_s3_bucket,
        prefix="",  # all items
    ):
        listing_requests.extend(page_items)

    assert len(listing_requests) == pagination_case.total_files

    created_files = [x[1] for x in created_files_data]
    queried_files = [x["Key"] for x in listing_requests]
    assert len(created_files) == len(queried_files)
    assert set(created_files) == set(queried_files)

    # fetch all items using the generator make sure it does not break
    generator_query = []
    async for s3_objects in storage_s3_client.list_all_objects_gen(
        storage_s3_bucket,
        prefix="",
    ):
        generator_query.extend(s3_objects)

    assert len(generator_query) == len(created_files)
