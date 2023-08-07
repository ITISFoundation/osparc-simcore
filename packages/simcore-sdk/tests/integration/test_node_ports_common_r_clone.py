# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import filecmp
import os
import re
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Final
from unittest.mock import AsyncMock
from uuid import uuid4

import aioboto3
import aiofiles
import pytest
from faker import Faker
from pydantic import AnyUrl, ByteSize, parse_obj_as
from servicelib.progress_bar import ProgressBarData
from servicelib.utils import logged_gather
from settings_library.r_clone import RCloneSettings
from simcore_sdk.node_ports_common import r_clone

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "storage",
]

pytest_simcore_ops_services_selection = [
    "minio",
    "adminer",
]


WAIT_FOR_S3_BACKEND_TO_UPDATE: Final[float] = 1.0


@pytest.fixture(
    params=[
        f"{uuid4()}.bin",
        "some funky name.txt",
        "öä$äö2-34 no extension",
    ]
)
def file_name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def local_file_for_download(upload_file_dir: Path, file_name: str) -> Path:
    return upload_file_dir / f"__local__{file_name}"


@pytest.fixture
async def cleanup_bucket_after_test(r_clone_settings: RCloneSettings) -> None:
    session = aioboto3.Session(
        aws_access_key_id=r_clone_settings.R_CLONE_S3.S3_ACCESS_KEY,
        aws_secret_access_key=r_clone_settings.R_CLONE_S3.S3_SECRET_KEY,
    )
    async with session.resource(
        "s3",
        endpoint_url=r_clone_settings.R_CLONE_S3.S3_ENDPOINT,
        use_ssl=r_clone_settings.R_CLONE_S3.S3_SECURE,
    ) as s_3:
        bucket = await s_3.Bucket(r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME)
        s3_objects = []
        async for s3_object in bucket.objects.all():
            s3_objects.append(s3_object)  # noqa: PERF402
        await asyncio.gather(*[o.delete() for o in s3_objects])


# UTILS


def _fake_s3_link(r_clone_settings: RCloneSettings, s3_object: str) -> AnyUrl:
    return parse_obj_as(
        AnyUrl,
        f"s3://{r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME}/{urllib.parse.quote(s3_object)}",
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
    chunk_size: int = parse_obj_as(ByteSize, "1mib"),  # noqa: B008
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
) -> None:
    # NOTE: progress is enforced only when uploading and only when using
    # total file sizes that are quite big, otherwise the test will fail
    # we ant to avoid this from being flaky.
    # Since using moto to mock the S3 api, downloading is way to fast.
    # Progress behaves as expected with CEPH and AWS S3 backends.

    progress_entries: list[float] = []

    async def _report_progress_upload(progress_value: float) -> None:
        print(">>>|", progress_value, "| ⏫")
        progress_entries.append(progress_value)

    async with ProgressBarData(
        steps=1, progress_report_cb=_report_progress_upload
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
) -> None:
    async def _report_progress_download(progress_value: float) -> None:
        print(">>>|", progress_value, "| ⏬")

    async with ProgressBarData(
        steps=1, progress_report_cb=_report_progress_download
    ) as progress_bar:
        await r_clone.sync_s3_to_local(
            r_clone_settings,
            progress_bar,
            local_directory_path=destination_dir,
            download_s3_link=s3_directory_link,
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
def dir_locally_created_files(tmp_path: Path, faker: Faker) -> Path:
    return _ensure_dir(tmp_path, faker, dir_prefix="source")


@pytest.fixture
def dir_downloaded_files_1(tmp_path: Path, faker: Faker) -> Path:
    return _ensure_dir(tmp_path, faker, dir_prefix="downloaded-1")


@pytest.fixture
def dir_downloaded_files_2(tmp_path: Path, faker: Faker) -> Path:
    return _ensure_dir(tmp_path, faker, dir_prefix="downloaded-2")


@pytest.mark.parametrize(
    "file_count, file_size, check_progress",
    [
        (0, parse_obj_as(ByteSize, "0"), False),
        (1, parse_obj_as(ByteSize, "1mib"), False),
        (2, parse_obj_as(ByteSize, "1mib"), False),
        (1, parse_obj_as(ByteSize, "1Gib"), True),
        (4, parse_obj_as(ByteSize, "500Mib"), True),
        (100, parse_obj_as(ByteSize, "20mib"), True),
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
) -> None:
    await _create_files_in_dir(dir_locally_created_files, file_count, file_size)

    # get s3 reference link
    directory_uuid = create_valid_file_uuid(f"{dir_locally_created_files}", Path(""))
    s3_directory_link = _fake_s3_link(r_clone_settings, directory_uuid)

    # run the test
    await _upload_local_dir_to_s3(
        r_clone_settings,
        s3_directory_link,
        dir_locally_created_files,
        check_progress=check_progress,
    )
    await _download_from_s3_to_local_dir(
        r_clone_settings, s3_directory_link, dir_downloaded_files_1
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
) -> None:
    generated_file_names: set[str] = await _create_files_in_dir(
        dir_locally_created_files,
        r_clone.S3_PARALLELISM * 3,
        parse_obj_as(ByteSize, "1kib"),
    )
    assert len(generated_file_names) > 0

    # get s3 reference link
    directory_uuid = create_valid_file_uuid(f"{dir_locally_created_files}", Path(""))
    s3_directory_link = _fake_s3_link(r_clone_settings, directory_uuid)

    # sync local to remote and check
    await _upload_local_dir_to_s3(
        r_clone_settings, s3_directory_link, dir_locally_created_files
    )
    await _download_from_s3_to_local_dir(
        r_clone_settings, s3_directory_link, dir_downloaded_files_1
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
        r_clone_settings, s3_directory_link, dir_locally_created_files
    )
    await _download_from_s3_to_local_dir(
        r_clone_settings, s3_directory_link, dir_downloaded_files_2
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
