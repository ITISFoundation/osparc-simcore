# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import math
import random
from collections.abc import AsyncIterable, Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from aws_library.s3._models import S3ObjectKey
from faker import Faker
from models_library.basic_types import SHA256Str
from models_library.progress_bar import ProgressReport
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.storage_utils import (
    FileIDDict,
    ProjectWithFilesParams,
)
from servicelib.progress_bar import ProgressBarData
from simcore_service_storage.constants import LinkType
from simcore_service_storage.models import FileMetaData
from simcore_service_storage.modules.db.file_meta_data import FileMetaDataRepository
from simcore_service_storage.modules.s3 import get_s3_client
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
def file_size() -> ByteSize:
    return TypeAdapter(ByteSize).validate_python("1")


@pytest.fixture
def mock_copy_transfer_cb() -> Callable[..., None]:
    def copy_transfer_cb(total_bytes_copied: int, *, file_name: str) -> None: ...

    return copy_transfer_cb


@pytest.fixture
async def cleanup_files_closure(
    simcore_s3_dsm: SimcoreS3DataManager, user_id: UserID
) -> AsyncIterable[Callable[[SimcoreS3FileID], None]]:
    to_remove: set[SimcoreS3FileID] = set()

    def _(file_id: SimcoreS3FileID) -> None:
        to_remove.add(file_id)

    yield _

    for file_id in to_remove:
        await simcore_s3_dsm.delete_file(user_id, file_id)


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test__copy_path_s3_s3(
    simcore_s3_dsm: SimcoreS3DataManager,
    create_directory_with_files: Callable[
        [str, ByteSize, int, int, ProjectID, NodeID],
        Awaitable[
            tuple[SimcoreS3FileID, tuple[NodeID, dict[SimcoreS3FileID, FileIDDict]]]
        ],
    ],
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    file_size: ByteSize,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    mock_copy_transfer_cb: Callable[..., None],
    sqlalchemy_async_engine: AsyncEngine,
    cleanup_files_closure: Callable[[SimcoreS3FileID], None],
):
    def _get_dest_file_id(src: SimcoreS3FileID) -> SimcoreS3FileID:
        copy_file_id = TypeAdapter(SimcoreS3FileID).validate_python(
            f"{Path(src).parent}/the-copy"
        )
        cleanup_files_closure(copy_file_id)
        return copy_file_id

    async def _copy_s3_path(s3_file_id_to_copy: SimcoreS3FileID) -> None:
        existing_fmd = await FileMetaDataRepository.instance(
            sqlalchemy_async_engine
        ).get(file_id=s3_file_id_to_copy)

        await simcore_s3_dsm._copy_path_s3_s3(  # noqa: SLF001
            user_id=user_id,
            src_fmd=existing_fmd,
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

    FILE_COUNT = 20
    SUBDIR_COUNT = 5
    s3_object, _ = await create_directory_with_files(
        dir_name="some-random",
        file_size_in_dir=file_size,
        subdir_count=SUBDIR_COUNT,
        file_count=FILE_COUNT,
        project_id=project_id,
        node_id=node_id,
    )

    s3_file_id_dir_src = TypeAdapter(SimcoreS3FileID).validate_python(s3_object)
    s3_file_id_dir_dst = _get_dest_file_id(s3_file_id_dir_src)

    await _count_files(s3_file_id_dir_dst, expected_count=0)
    await _copy_s3_path(s3_file_id_dir_src)
    await _count_files(s3_file_id_dir_dst, expected_count=FILE_COUNT)

    # using a single file

    _, simcore_file_id = await upload_file(file_size, "a_file_name")
    await _copy_s3_path(simcore_file_id)


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
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


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_search_files(
    simcore_s3_dsm: SimcoreS3DataManager,
    upload_file: Callable[..., Awaitable[tuple[Path, SimcoreS3FileID]]],
    file_size: ByteSize,
    user_id: UserID,
    project_id: ProjectID,
    faker: Faker,
):
    # Upload files with different patterns
    test_files = [
        ("test_file1.txt", "*.txt"),
        ("test_file2.txt", "*.txt"),
        ("document.pdf", "*.pdf"),
        ("data_file.csv", "data_*.csv"),
        ("backup_file.bak", "backup_*"),
        ("config.json", "*.json"),
        ("temp_data.tmp", "temp_*"),
    ]

    uploaded_files = []
    for file_name, _ in test_files:
        checksum: SHA256Str = TypeAdapter(SHA256Str).validate_python(faker.sha256())
        _, file_id = await upload_file(file_size, file_name, sha256_checksum=checksum)
        uploaded_files.append((file_name, file_id, checksum))

    # Test 1: Search for all .txt files
    txt_results = []
    async for page in simcore_s3_dsm.search_files(
        user_id=user_id,
        filename_pattern="*.txt",
        project_id=project_id,
        items_per_page=10,
    ):
        txt_results.extend(page)

    # Should find 2 txt files
    assert len(txt_results) == 2
    txt_names = {file.file_name for file in txt_results}
    assert txt_names == {"test_file1.txt", "test_file2.txt"}

    # Test 2: Search with specific prefix pattern
    data_results = []
    async for page in simcore_s3_dsm.search_files(
        user_id=user_id,
        filename_pattern="data_*",
        project_id=project_id,
        items_per_page=10,
    ):
        data_results.extend(page)

    # Should find 1 data file
    assert len(data_results) == 1
    assert data_results[0].file_name == "data_file.csv"

    # Test 3: Search with pattern that matches multiple extensions
    temp_results = []
    async for page in simcore_s3_dsm.search_files(
        user_id=user_id,
        filename_pattern="temp_*",
        project_id=project_id,
        items_per_page=10,
    ):
        temp_results.extend(page)

    # Should find 1 temp file
    assert len(temp_results) == 1
    assert temp_results[0].file_name == "temp_data.tmp"

    # Test 4: Search with pattern that doesn't match anything
    no_match_results = []
    async for page in simcore_s3_dsm.search_files(
        user_id=user_id,
        filename_pattern="nonexistent_*",
        project_id=project_id,
        items_per_page=10,
    ):
        no_match_results.extend(page)

    assert len(no_match_results) == 0

    # Test 5: Search without project_id restriction (all accessible projects)
    all_results = []
    async for page in simcore_s3_dsm.search_files(
        user_id=user_id,
        filename_pattern="*",
        items_per_page=10,
    ):
        all_results.extend(page)

    # Should find at least our uploaded files
    assert len(all_results) >= len(test_files)

    # Verify that each result has expected FileMetaData structure
    for file_meta in all_results:
        assert isinstance(file_meta, FileMetaData)
        assert file_meta.file_name is not None
        assert file_meta.file_id is not None
        assert file_meta.user_id == user_id
        assert file_meta.project_id is not None

    # Test 6: Test pagination with small page size
    paginated_results = []
    page_count = 0
    async for page in simcore_s3_dsm.search_files(
        user_id=user_id,
        filename_pattern="*",
        project_id=project_id,
        items_per_page=2,  # Small page size to test pagination
    ):
        paginated_results.extend(page)
        page_count += 1
        # Each page should have at most 2 items
        assert len(page) <= 2

    # Should have multiple pages and all our files
    assert page_count >= 4  # At least 7 files / 2 per page = 4 pages
    assert len(paginated_results) == len(test_files)


@pytest.fixture
async def paths_for_export(
    random_project_with_files: Callable[
        [ProjectWithFilesParams],
        Awaitable[
            tuple[dict[str, Any], dict[NodeID, dict[SimcoreS3FileID, FileIDDict]]]
        ],
    ],
) -> set[SimcoreS3FileID]:
    _, file_mapping = await random_project_with_files(
        ProjectWithFilesParams(
            num_nodes=2,
            allowed_file_sizes=(TypeAdapter(ByteSize).validate_python("1KiB"),),
            workspace_files_count=4,
        )
    )

    to_export: set[SimcoreS3FileID] = set()

    for file_id_dict in file_mapping.values():
        to_export |= file_id_dict.keys()

    return to_export


def _get_folder_and_files_selection(
    paths_for_export: set[SimcoreS3FileID],
) -> list[S3ObjectKey]:
    # select 10 % of files

    random_files: list[SimcoreS3FileID] = [
        random.choice(list(paths_for_export))  # noqa: S311
        for _ in range(math.ceil(0.1 * len(paths_for_export)))
    ]

    all_containing_folders: set[SimcoreS3FileID] = {
        TypeAdapter(S3ObjectKey).validate_python(f"{Path(f).parent}")
        for f in random_files
    }

    element_selection = random_files + list(all_containing_folders)

    # ensure all elements are duplicated and shuffled
    duplicate_selection = [*element_selection, *element_selection]
    random.shuffle(duplicate_selection)  # type: ignore
    return duplicate_selection


async def _get_fmds_count(
    connection: AsyncEngine,
) -> int:
    result = await FileMetaDataRepository.instance(connection).list_fmds()
    return len(result)


async def _assert_meta_data_entries_count(
    connection: AsyncEngine, *, count: int
) -> None:
    assert (await _get_fmds_count(connection)) == count


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_create_s3_export(
    simcore_s3_dsm: SimcoreS3DataManager,
    user_id: UserID,
    paths_for_export: set[SimcoreS3FileID],
    sqlalchemy_async_engine: AsyncEngine,
    cleanup_files_closure: Callable[[SimcoreS3FileID], None],
):
    initial_fmd_count = await _get_fmds_count(sqlalchemy_async_engine)
    all_files_to_export = _get_folder_and_files_selection(paths_for_export)
    selection_to_export = {
        S3ObjectKey(project_id)
        for project_id in {Path(p).parents[-2] for p in all_files_to_export}
    }

    reports: list[ProgressReport] = []

    async def _progress_cb(report: ProgressReport) -> None:
        reports.append(report)

    await _assert_meta_data_entries_count(
        sqlalchemy_async_engine, count=initial_fmd_count
    )

    async with ProgressBarData(
        num_steps=1, description="data export", progress_report_cb=_progress_cb
    ) as root_progress_bar:
        file_id = await simcore_s3_dsm.create_s3_export(
            user_id, selection_to_export, progress_bar=root_progress_bar
        )
    cleanup_files_closure(file_id)
    # count=2 -> the direcotory and the .zip export
    await _assert_meta_data_entries_count(
        sqlalchemy_async_engine, count=initial_fmd_count + 1
    )

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
        async with ProgressBarData(
            num_steps=1, description="data export"
        ) as progress_bar:
            await simcore_s3_dsm.create_s3_export(
                user_id, [], progress_bar=progress_bar
            )
    await _assert_meta_data_entries_count(sqlalchemy_async_engine, count=0)
