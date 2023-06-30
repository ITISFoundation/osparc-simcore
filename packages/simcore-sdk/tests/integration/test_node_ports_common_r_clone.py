# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import filecmp
import os
import re
import urllib.parse
from pathlib import Path
from typing import Callable, Final
from uuid import uuid4

import aiofiles
import pytest
from faker import Faker
from models_library.api_schemas_storage import FileUploadLinks, FileUploadSchema
from pydantic import AnyUrl, ByteSize, parse_obj_as
from pytest import FixtureRequest
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
def file_name(request: FixtureRequest) -> str:
    return request.param  # type: ignore


@pytest.fixture
def local_file_for_download(upload_file_dir: Path, file_name: str) -> Path:
    local_file_path = upload_file_dir / f"__local__{file_name}"
    return local_file_path


# UTILS


def _fake_upload_file_link(
    r_clone_settings: RCloneSettings, s3_object: str
) -> FileUploadSchema:
    return FileUploadSchema(
        chunk_size=ByteSize(0),
        urls=[
            parse_obj_as(
                AnyUrl,
                f"s3://{r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME}/{urllib.parse.quote(s3_object)}",
            )
        ],
        links=FileUploadLinks(
            abort_upload=parse_obj_as(AnyUrl, "https://www.fakeabort.com"),
            complete_upload=parse_obj_as(AnyUrl, "https://www.fakecomplete.com"),
        ),
    )


def test_s3_url_quote_and_unquote():
    """This test was added to validate quotation operations in _fake_upload_file_link
    against unquotation operation in

    """
    src = "53a35372-d44d-4d2e-8319-b40db5f31ce0/2f67d5cb-ea9c-4f8c-96ef-eae8445a0fe7/6fa73b0f-4006-46c6-9847-967b45ff3ae7.bin"
    # as in _fake_upload_file_link
    url = f"s3://simcore/{urllib.parse.quote(src)}"

    # as in sync_local_to_s3
    unquoted_url = urllib.parse.unquote(url)
    truncated_url = re.sub(r"^s3://", "", unquoted_url)
    assert truncated_url == f"simcore/{src}"


async def _create_random_binary_file(
    file_path: Path,
    file_size: ByteSize,
    chunk_size: int = parse_obj_as(ByteSize, "1mib"),
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
    s3_directory_link: FileUploadSchema,
    source_dir: Path,
) -> None:
    async def _report_progress_upload(progress_value: float) -> None:
        print(">>>|", progress_value, "| ⏫")

    async with ProgressBarData(
        steps=1, progress_report_cb=_report_progress_upload
    ) as progress_bar:
        await r_clone.sync_local_to_s3(
            r_clone_settings,
            progress_bar,
            local_directory_path=source_dir,
            upload_directory_link=s3_directory_link,
        )


async def _download_from_s3_to_local_dir(
    r_clone_settings: RCloneSettings,
    s3_directory_link: FileUploadSchema,
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
            download_directory_link=s3_directory_link,
        )


def _directories_have_the_same_content(
    dir_1: Path, dir_2: Path, *, expected_file_names: set[str]
) -> bool:
    filecmp.clear_cache()
    return all(
        filecmp.cmp(dir_1 / file_name, dir_2 / file_name, shallow=False)
        for file_name in expected_file_names
    )


@pytest.mark.parametrize(
    "file_count, file_size",
    [
        (0, parse_obj_as(ByteSize, "0")),
        (1, parse_obj_as(ByteSize, "1mib")),
        (2, parse_obj_as(ByteSize, "1mib")),
        # (1, parse_obj_as(ByteSize, "1Gib")),
        # (4, parse_obj_as(ByteSize, "500Mib")),
        # (100, parse_obj_as(ByteSize, "20mib")),
    ],
)
async def test_local_to_remote_to_local(
    r_clone_settings: RCloneSettings,
    create_valid_file_uuid: Callable[[str, Path], str],
    tmp_path: Path,
    faker: Faker,
    file_count: int,
    file_size: ByteSize,
) -> None:
    # locally created files directory
    generated_files_dir: Path = tmp_path / f"source-{faker.uuid4()}"
    generated_files_dir.mkdir(parents=True, exist_ok=True)
    assert generated_files_dir.exists()

    # downloaded files directory
    downloaded_files_dir = tmp_path / f"local-destination-{faker.uuid4()}"
    downloaded_files_dir.mkdir(parents=True, exist_ok=True)
    assert downloaded_files_dir.exists()

    generated_file_names: set[str] = await _create_files_in_dir(
        generated_files_dir, file_count, file_size
    )

    # get s3 reference link
    directory_uuid = create_valid_file_uuid(f"{generated_files_dir}", Path(""))
    s3_directory_link = _fake_upload_file_link(r_clone_settings, directory_uuid)

    # run the test
    await _upload_local_dir_to_s3(
        r_clone_settings, s3_directory_link, generated_files_dir
    )
    await _download_from_s3_to_local_dir(
        r_clone_settings, s3_directory_link, downloaded_files_dir
    )
    assert _directories_have_the_same_content(
        generated_files_dir,
        downloaded_files_dir,
        expected_file_names=generated_file_names,
    )

    # check same file contents after upload and download
    assert filecmp.cmp(local_file, local_download_file)
