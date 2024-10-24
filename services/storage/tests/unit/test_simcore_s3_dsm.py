# pylint:disable=protected-access
# pylint:disable=redefined-outer-name

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path

import pytest
from aiopg.sa.engine import Engine
from faker import Faker
from models_library.api_schemas_storage import FileUploadSchema
from models_library.basic_types import SHA256Str
from models_library.projects_nodes_io import SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from simcore_service_storage import db_file_meta_data
from simcore_service_storage.models import FileMetaData
from simcore_service_storage.s3 import get_s3_client
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
def file_size() -> ByteSize:
    return TypeAdapter(ByteSize).validate_python("1")


@pytest.fixture
def mock_copy_transfer_cb() -> Callable[..., None]:
    def copy_transfer_cb(total_bytes_copied: int, *, file_name: str) -> None:
        ...

    return copy_transfer_cb


async def test__copy_path_s3_s3(
    simcore_s3_dsm: SimcoreS3DataManager,
    create_directory_with_files: Callable[
        ..., AbstractAsyncContextManager[FileUploadSchema]
    ],
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    file_size: ByteSize,
    user_id: UserID,
    mock_copy_transfer_cb: Callable[..., None],
    aiopg_engine: Engine,
):
    def _get_dest_file_id(src: SimcoreS3FileID) -> SimcoreS3FileID:
        return TypeAdapter(SimcoreS3FileID).validate_python(
            f"{Path(src).parent}/the-copy"
        )

    async def _copy_s3_path(s3_file_id_to_copy: SimcoreS3FileID) -> None:
        async with aiopg_engine.acquire() as conn:
            exiting_fmd = await db_file_meta_data.get(conn, s3_file_id_to_copy)

        await simcore_s3_dsm._copy_path_s3_s3(  # noqa: SLF001
            user_id=user_id,
            src_fmd=exiting_fmd,
            dst_file_id=_get_dest_file_id(s3_file_id_to_copy),
            bytes_transfered_cb=mock_copy_transfer_cb,
        )

    async def _count_files(s3_file_id: SimcoreS3FileID, expected_count: int) -> None:
        s3_client = get_s3_client(simcore_s3_dsm.app)
        counted_files = 0
        async for s3_objects in s3_client.list_objects_paginated(
            bucket=simcore_s3_dsm.simcore_bucket_name, prefix=s3_file_id
        ):
            counted_files += len(s3_objects)

        assert counted_files == expected_count

    # using directory

    FILE_COUNT = 4
    SUBDIR_COUNT = 5
    async with create_directory_with_files(
        dir_name="some-random",
        file_size_in_dir=file_size,
        subdir_count=SUBDIR_COUNT,
        file_count=FILE_COUNT,
    ) as directory_file_upload:
        assert len(directory_file_upload.urls) == 1
        assert directory_file_upload.urls[0].path
        s3_object = directory_file_upload.urls[0].path.lstrip("/")

        s3_file_id_dir_src = TypeAdapter(SimcoreS3FileID).validate_python(s3_object)
        s3_file_id_dir_dst = _get_dest_file_id(s3_file_id_dir_src)

        await _count_files(s3_file_id_dir_dst, expected_count=0)
        await _copy_s3_path(s3_file_id_dir_src)
        await _count_files(s3_file_id_dir_dst, expected_count=FILE_COUNT * SUBDIR_COUNT)

    # using a single file

    _, simcore_file_id = await upload_file(file_size, "a_file_name")
    await _copy_s3_path(simcore_file_id)


async def test_upload_and_search(
    simcore_s3_dsm: SimcoreS3DataManager,
    upload_file: Callable[..., Awaitable[tuple[Path, SimcoreS3FileID]]],
    file_size: ByteSize,
    user_id: UserID,
    faker: Faker,
):
    checksum: SHA256Str = TypeAdapter(SHA256Str).validate_python(faker.sha256())
    _, _ = await upload_file(file_size, "file1", sha256_checksum=checksum)
    _, _ = await upload_file(file_size, "file2", sha256_checksum=checksum)

    files: list[FileMetaData] = await simcore_s3_dsm.search_owned_files(
        user_id=user_id, file_id_prefix="", sha256_checksum=checksum
    )
    assert len(files) == 2
    for file in files:
        assert file.sha256_checksum == checksum
        assert file.file_name in {"file1", "file2"}
