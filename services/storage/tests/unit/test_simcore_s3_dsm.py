# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import math
import random
from collections.abc import AsyncIterable, Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path

import pytest
from faker import Faker
from models_library.basic_types import SHA256Str
from models_library.progress_bar import ProgressReport
from models_library.projects_nodes_io import SimcoreS3FileID, StorageFileID
from models_library.storage_schemas import FileUploadSchema
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from simcore_service_storage.constants import LinkType
from simcore_service_storage.models import FileMetaData
from simcore_service_storage.modules.db import file_meta_data
from simcore_service_storage.modules.s3 import get_s3_client
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from sqlalchemy.ext.asyncio import AsyncEngine

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


@pytest.fixture
async def cleanup_when_done(
    simcore_s3_dsm: SimcoreS3DataManager, user_id: UserID
) -> AsyncIterable[Callable[[SimcoreS3FileID], None]]:
    to_remove: set[SimcoreS3FileID] = set()

    def _(file_id: SimcoreS3FileID) -> None:
        to_remove.add(file_id)

    yield _

    for file_id in to_remove:
        await simcore_s3_dsm.delete_file(user_id, file_id)


async def test__copy_path_s3_s3(
    simcore_s3_dsm: SimcoreS3DataManager,
    create_directory_with_files: Callable[
        ..., AbstractAsyncContextManager[FileUploadSchema]
    ],
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    file_size: ByteSize,
    user_id: UserID,
    mock_copy_transfer_cb: Callable[..., None],
    sqlalchemy_async_engine: AsyncEngine,
    cleanup_when_done: Callable[[SimcoreS3FileID], None],
):
    def _get_dest_file_id(src: SimcoreS3FileID) -> SimcoreS3FileID:
        copy_file_id = TypeAdapter(SimcoreS3FileID).validate_python(
            f"{Path(src).parent}/the-copy"
        )
        cleanup_when_done(copy_file_id)
        return copy_file_id

    async def _copy_s3_path(s3_file_id_to_copy: SimcoreS3FileID) -> None:
        async with sqlalchemy_async_engine.connect() as conn:
            exiting_fmd = await file_meta_data.get(conn, s3_file_id_to_copy)

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


@pytest.fixture
async def paths_for_export(
    create_empty_directory: Callable[..., Awaitable[FileUploadSchema]],
    populate_directory: Callable[..., Awaitable[set[SimcoreS3FileID]]],
    delete_directory: Callable[..., Awaitable[None]],
) -> AsyncIterable[set[StorageFileID]]:
    dir_name = "data_to_export"

    directory_file_upload: FileUploadSchema = await create_empty_directory(
        dir_name=dir_name
    )

    uploaded_files: set[StorageFileID] = await populate_directory(
        TypeAdapter(ByteSize).validate_python("10MiB"), dir_name, 10, 4
    )

    yield uploaded_files

    await delete_directory(directory_file_upload=directory_file_upload)


def _get_folder_and_files_selection(
    paths_for_export: set[StorageFileID],
) -> list[StorageFileID]:
    # select 10 % of files

    random_files: list[StorageFileID] = [
        random.choice(list(paths_for_export))  # noqa: S311
        for _ in range(math.ceil(0.1 * len(paths_for_export)))
    ]

    all_containing_folders: set[StorageFileID] = {
        TypeAdapter(StorageFileID).validate_python(f"{Path(f).parent}")
        for f in random_files
    }

    element_selection = random_files + list(all_containing_folders)

    # ensure all elements are duplicated and shuffled
    duplicate_selection = [*element_selection, *element_selection]
    random.shuffle(duplicate_selection)  # type: ignore
    return duplicate_selection


async def _assert_meta_data_entries_count(
    connection: AsyncEngine, *, count: int
) -> None:
    async with connection.connect() as conn:
        result = await file_meta_data.list_fmds(conn)
        assert len(result) == count


async def test_create_s3_export(
    simcore_s3_dsm: SimcoreS3DataManager,
    user_id: UserID,
    paths_for_export: set[StorageFileID],
    sqlalchemy_async_engine: AsyncEngine,
    cleanup_when_done: Callable[[SimcoreS3FileID], None],
):
    selection_to_export = _get_folder_and_files_selection(paths_for_export)

    reports: list[ProgressReport] = []

    async def _progress_cb(report: ProgressReport) -> None:
        reports.append(report)

    await _assert_meta_data_entries_count(sqlalchemy_async_engine, count=1)
    file_id = await simcore_s3_dsm.create_s3_export(
        user_id, selection_to_export, progress_cb=_progress_cb
    )
    cleanup_when_done(file_id)
    # count=2 -> the direcotory and the .zip export
    await _assert_meta_data_entries_count(sqlalchemy_async_engine, count=2)

    download_link = await simcore_s3_dsm.create_file_download_link(
        user_id, file_id, LinkType.PRESIGNED
    )

    assert file_id in f"{download_link}"

    assert reports[-1].actual_value == 1


@pytest.fixture
def mock_create_and_upload_export_raises_error(mocker: MockerFixture) -> None:
    async def _raise_error(*args, **kwarts) -> None:
        msg = "failing as expected"
        raise RuntimeError(msg)

    mocker.patch(
        "simcore_service_storage.simcore_s3_dsm.create_and_upload_export",
        side_effect=_raise_error,
    )


async def test_create_s3_export_abort_upload_upon_error(
    mock_create_and_upload_export_raises_error: None,
    simcore_s3_dsm: SimcoreS3DataManager,
    user_id: UserID,
    sqlalchemy_async_engine: AsyncEngine,
):
    await _assert_meta_data_entries_count(sqlalchemy_async_engine, count=0)
    with pytest.raises(RuntimeError, match="failing as expected"):
        await simcore_s3_dsm.create_s3_export(user_id, [], progress_cb=None)
    await _assert_meta_data_entries_count(sqlalchemy_async_engine, count=0)
