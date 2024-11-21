# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import filecmp
import os
import re
import urllib.parse
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Final
from unittest.mock import AsyncMock
from uuid import uuid4

import aioboto3
import aiofiles
import pytest
from faker import Faker
from models_library.basic_types import IDStr
from models_library.progress_bar import ProgressReport
from pydantic import AnyUrl, ByteSize, TypeAdapter
from servicelib.file_utils import remove_directory
from servicelib.progress_bar import ProgressBarData
from servicelib.utils import logged_gather
from settings_library.r_clone import RCloneSettings
from simcore_sdk.node_ports_common import r_clone

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "storage",
    "redis",
]

pytest_simcore_ops_services_selection = [
    "minio",
    "adminer",
]


WAIT_FOR_S3_BACKEND_TO_UPDATE: Final[float] = 1.0


@pytest.fixture
async def cleanup_bucket_after_test(
    r_clone_settings: RCloneSettings,
) -> AsyncIterator[None]:
    session = aioboto3.Session(
        aws_access_key_id=r_clone_settings.R_CLONE_S3.S3_ACCESS_KEY,
        aws_secret_access_key=r_clone_settings.R_CLONE_S3.S3_SECRET_KEY,
    )

    yield

    async with session.client(
        "s3", endpoint_url=f"{r_clone_settings.R_CLONE_S3.S3_ENDPOINT}"
    ) as s3_client:
        # List all object versions
        paginator = s3_client.get_paginator("list_object_versions")
        async for page in paginator.paginate(
            Bucket=r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME
        ):
            # Prepare delete markers and versions for deletion
            delete_markers = page.get("DeleteMarkers", [])
            versions = page.get("Versions", [])

            objects_to_delete = [
                {"Key": obj["Key"], "VersionId": obj["VersionId"]}
                for obj in delete_markers + versions
            ]

            # Perform deletion
            if objects_to_delete:
                await s3_client.delete_objects(
                    Bucket=r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME,
                    Delete={"Objects": objects_to_delete, "Quiet": True},
                )


def _fake_s3_link(r_clone_settings: RCloneSettings, s3_object: str) -> AnyUrl:
    return TypeAdapter(AnyUrl).validate_python(
        f"s3://{r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME}/{urllib.parse.quote(s3_object)}"
    )


def test_s3_url_quote_and_unquote():
    """This test was added to validate quotation operations in _fake_s3_link
    against unquotation operation in

    """
    src = "53a35372-d44d-4d2e-8319-b40db5f31ce0/2f67d5cb-ea9c-4f8c-96ef-eae8445a0fe7/6fa73b0f-4006-46c6-9847-967b45ff3ae7.bin"
    # as in _fake_s3_link
    url = f"s3://simcore/{urllib.parse.quote(src)}"

    # as in sync_local_to_s3
    unquoted_url = urllib.parse.unquote(url)
    truncated_url = re.sub(r"^s3://", "", unquoted_url)
    assert truncated_url == f"simcore/{src}"


async def _create_random_binary_file(
    file_path: Path,
    file_size: ByteSize,
    # NOTE: bigger files get created faster with bigger chunk_size
    chunk_size: int = TypeAdapter(ByteSize).validate_python("1mib"),
):
    async with aiofiles.open(file_path, mode="wb") as file:
        bytes_written = 0
        while bytes_written < file_size:
            remaining_bytes = file_size - bytes_written
            current_chunk_size = min(chunk_size, remaining_bytes)
            await file.write(os.urandom(current_chunk_size))
            bytes_written += current_chunk_size
        assert bytes_written == file_size


async def _create_file_of_size(
    tmp_path: Path, *, name: str, file_size: ByteSize
) -> Path:
    file: Path = tmp_path / name
    if not file.parent.exists():
        file.parent.mkdir(parents=True, exist_ok=True)

    await _create_random_binary_file(file, file_size)
    assert file.exists()
    assert file.stat().st_size == file_size
    return file


async def _create_files_in_dir(
    target_dir: Path, file_count: int, file_size: ByteSize
) -> set[str]:
    results: list[Path] = await logged_gather(
        *[
            _create_file_of_size(target_dir, name=f"{i}-file.bin", file_size=file_size)
            for i in range(file_count)
        ],
        max_concurrency=10,
    )
    return {x.name for x in results}


async def _upload_local_dir_to_s3(
    r_clone_settings: RCloneSettings,
    s3_directory_link: AnyUrl,
    source_dir: Path,
    *,
    check_progress: bool = False,
    faker: Faker,
) -> None:
    # NOTE: progress is enforced only when uploading and only when using
    # total file sizes that are quite big, otherwise the test will fail
    # we ant to avoid this from being flaky.
    # Since using moto to mock the S3 api, downloading is way to fast.
    # Progress behaves as expected with CEPH and AWS S3 backends.

    progress_entries: list[ProgressReport] = []

    async def _report_progress_upload(report: ProgressReport) -> None:
        print(">>>|", report, "| ⏫")
        progress_entries.append(report)

    async with ProgressBarData(
        num_steps=1,
        progress_report_cb=_report_progress_upload,
        description=IDStr(faker.pystr()),
    ) as progress_bar:
        await r_clone.sync_local_to_s3(
            r_clone_settings,
            progress_bar,
            local_directory_path=source_dir,
            upload_s3_link=s3_directory_link,
            debug_logs=True,
        )
    if check_progress:
        # NOTE: a progress of 1 is always sent by the progress bar
        # we want to check that rclone also reports some progress entries
        assert len(progress_entries) > 1


async def _download_from_s3_to_local_dir(
    r_clone_settings: RCloneSettings,
    s3_directory_link: AnyUrl,
    destination_dir: Path,
    faker: Faker,
) -> None:
    async def _report_progress_download(report: ProgressReport) -> None:
        print(">>>|", report, "| ⏬")

    async with ProgressBarData(
        num_steps=1,
        progress_report_cb=_report_progress_download,
        description=IDStr(faker.pystr()),
    ) as progress_bar:
        await r_clone.sync_s3_to_local(
            r_clone_settings,
            progress_bar,
            local_directory_path=destination_dir,
            download_s3_link=f"{s3_directory_link}",
            debug_logs=True,
        )


def _directories_have_the_same_content(dir_1: Path, dir_2: Path) -> bool:
    names_in_dir_1 = {x.name for x in dir_1.glob("*")}
    names_in_dir_2 = {x.name for x in dir_2.glob("*")}
    if names_in_dir_1 != names_in_dir_2:
        return False

    filecmp.clear_cache()

    compare_results: list[bool] = []

    for file_name in names_in_dir_1:
        f1 = dir_1 / file_name
        f2 = dir_2 / file_name

        # when there is a broken symlink, which we want to sync, filecmp does not work
        is_broken_symlink = (
            not f1.exists() and f1.is_symlink() and not f2.exists() and f2.is_symlink()
        )

        if is_broken_symlink:
            compare_results.append(True)
        else:
            compare_results.append(filecmp.cmp(f1, f2, shallow=False))

    return all(compare_results)


def _ensure_dir(tmp_path: Path, faker: Faker, *, dir_prefix: str) -> Path:
    generated_files_dir: Path = tmp_path / f"{dir_prefix}-{faker.uuid4()}"
    generated_files_dir.mkdir(parents=True, exist_ok=True)
    assert generated_files_dir.exists()
    return generated_files_dir


@pytest.fixture
async def dir_locally_created_files(
    tmp_path: Path, faker: Faker
) -> AsyncIterator[Path]:
    path = _ensure_dir(tmp_path, faker, dir_prefix="source")
    yield path
    await remove_directory(path)


@pytest.fixture
async def dir_downloaded_files_1(tmp_path: Path, faker: Faker) -> AsyncIterator[Path]:
    path = _ensure_dir(tmp_path, faker, dir_prefix="downloaded-1")
    yield path
    await remove_directory(path)


@pytest.fixture
async def dir_downloaded_files_2(tmp_path: Path, faker: Faker) -> AsyncIterator[Path]:
    path = _ensure_dir(tmp_path, faker, dir_prefix="downloaded-2")
    yield path
    await remove_directory(path)


@pytest.mark.parametrize(
    "file_count, file_size, check_progress",
    [
        (0, TypeAdapter(ByteSize).validate_python("0"), False),
        (1, TypeAdapter(ByteSize).validate_python("1mib"), False),
        (2, TypeAdapter(ByteSize).validate_python("1mib"), False),
        (1, TypeAdapter(ByteSize).validate_python("1Gib"), True),
        pytest.param(
            4,
            TypeAdapter(ByteSize).validate_python("500Mib"),
            True,
            marks=pytest.mark.heavy_load,
        ),
        pytest.param(
            100,
            TypeAdapter(ByteSize).validate_python("20mib"),
            True,
            marks=pytest.mark.heavy_load,
        ),
    ],
)
async def test_local_to_remote_to_local(
    r_clone_settings: RCloneSettings,
    create_valid_file_uuid: Callable[[str, Path], str],
    dir_locally_created_files: Path,
    dir_downloaded_files_1: Path,
    file_count: int,
    file_size: ByteSize,
    check_progress: bool,
    cleanup_bucket_after_test: None,
    faker: Faker,
) -> None:
    await _create_files_in_dir(dir_locally_created_files, file_count, file_size)

    # get s3 reference link
    directory_uuid = create_valid_file_uuid(f"{dir_locally_created_files}", Path())
    s3_directory_link = _fake_s3_link(r_clone_settings, directory_uuid)

    # run the test
    await _upload_local_dir_to_s3(
        r_clone_settings,
        s3_directory_link,
        dir_locally_created_files,
        check_progress=check_progress,
        faker=faker,
    )
    await _download_from_s3_to_local_dir(
        r_clone_settings, s3_directory_link, dir_downloaded_files_1, faker=faker
    )
    assert _directories_have_the_same_content(
        dir_locally_created_files, dir_downloaded_files_1
    )


def _change_content_of_one_file(
    dir_locally_created_files: Path, generated_file_names: set[str]
) -> None:
    a_generated_file = next(iter(generated_file_names))
    (dir_locally_created_files / a_generated_file).write_bytes(os.urandom(10))


def _change_content_of_all_file(
    dir_locally_created_files: Path, generated_file_names: set[str]
) -> None:
    for file_name in generated_file_names:
        (dir_locally_created_files / file_name).unlink()
        (dir_locally_created_files / file_name).write_bytes(os.urandom(10))


def _remove_one_file(
    dir_locally_created_files: Path, generated_file_names: set[str]
) -> None:
    a_generated_file = next(iter(generated_file_names))
    (dir_locally_created_files / a_generated_file).unlink()


def _rename_one_file(
    dir_locally_created_files: Path, generated_file_names: set[str]
) -> None:
    a_generated_file = next(iter(generated_file_names))
    (dir_locally_created_files / a_generated_file).rename(
        dir_locally_created_files / f"renamed-{a_generated_file}"
    )


def _add_a_new_file(
    dir_locally_created_files: Path, generated_file_names: set[str]
) -> None:
    (dir_locally_created_files / "new_file.bin").write_bytes(os.urandom(10))


def _remove_all_files(
    dir_locally_created_files: Path, generated_file_names: set[str]
) -> None:
    for file_name in generated_file_names:
        (dir_locally_created_files / file_name).unlink()


def _regression_add_broken_symlink(
    dir_locally_created_files: Path, generated_file_names: set[str]
) -> None:
    # NOTE: if rclone tries to copy a link that does not exist an error is raised
    path_does_not_exist_on_fs = Path(f"/tmp/missing-{uuid4()}")  # noqa: S108
    assert not path_does_not_exist_on_fs.exists()

    broken_symlink = dir_locally_created_files / "missing.link"
    assert not broken_symlink.exists()
    os.symlink(f"{path_does_not_exist_on_fs}", f"{broken_symlink}")


@pytest.mark.parametrize(
    "changes_callable",
    [
        _change_content_of_one_file,
        _change_content_of_all_file,
        _remove_one_file,
        _remove_all_files,
        _rename_one_file,
        _add_a_new_file,
        _regression_add_broken_symlink,
    ],
)
async def test_overwrite_an_existing_file_and_sync_again(
    r_clone_settings: RCloneSettings,
    create_valid_file_uuid: Callable[[str, Path], str],
    dir_locally_created_files: Path,
    dir_downloaded_files_1: Path,
    dir_downloaded_files_2: Path,
    changes_callable: Callable[[Path, set[str]], None],
    cleanup_bucket_after_test: None,
    faker: Faker,
) -> None:
    generated_file_names: set[str] = await _create_files_in_dir(
        dir_locally_created_files,
        r_clone_settings.R_CLONE_OPTION_TRANSFERS * 3,
        TypeAdapter(ByteSize).validate_python("1kib"),
    )
    assert len(generated_file_names) > 0

    # get s3 reference link
    directory_uuid = create_valid_file_uuid(f"{dir_locally_created_files}", Path())
    s3_directory_link = _fake_s3_link(r_clone_settings, directory_uuid)

    # sync local to remote and check
    await _upload_local_dir_to_s3(
        r_clone_settings, s3_directory_link, dir_locally_created_files, faker=faker
    )
    await _download_from_s3_to_local_dir(
        r_clone_settings, s3_directory_link, dir_downloaded_files_1, faker=faker
    )
    assert _directories_have_the_same_content(
        dir_locally_created_files, dir_downloaded_files_1
    )

    # make some changes to local content
    changes_callable(dir_locally_created_files, generated_file_names)

    # ensure local content changed form remote content
    assert not _directories_have_the_same_content(
        dir_locally_created_files, dir_downloaded_files_1
    )

    # upload and check new local and new remote are in sync
    await _upload_local_dir_to_s3(
        r_clone_settings, s3_directory_link, dir_locally_created_files, faker=faker
    )
    await _download_from_s3_to_local_dir(
        r_clone_settings, s3_directory_link, dir_downloaded_files_2, faker=faker
    )
    assert _directories_have_the_same_content(
        dir_locally_created_files, dir_downloaded_files_2
    )
    # check that old remote and new remote are nto the same
    assert not _directories_have_the_same_content(
        dir_downloaded_files_1, dir_downloaded_files_2
    )


async def test_raises_error_if_local_directory_path_is_a_file(
    tmp_path: Path, faker: Faker, cleanup_bucket_after_test: None
):
    file_path = await _create_file_of_size(
        tmp_path, name=f"test{faker.uuid4()}.bin", file_size=ByteSize(1)
    )
    with pytest.raises(r_clone.RCloneDirectoryNotFoundError):
        await r_clone.sync_local_to_s3(
            r_clone_settings=AsyncMock(),
            progress_bar=AsyncMock(),
            local_directory_path=file_path,
            upload_s3_link=AsyncMock(),
            debug_logs=True,
        )
    with pytest.raises(r_clone.RCloneDirectoryNotFoundError):
        await r_clone.sync_s3_to_local(
            r_clone_settings=AsyncMock(),
            progress_bar=AsyncMock(),
            local_directory_path=file_path,
            download_s3_link=AsyncMock(),
            debug_logs=True,
        )
