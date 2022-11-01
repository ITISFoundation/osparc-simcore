# pylint:disable=redefined-outer-name,unused-argument

import asyncio
import hashlib
import os
import tempfile
import uuid
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterator

import pytest
from simcore_service_webserver.exporter.archiving import (
    unzip_folder,
    validate_osparc_import_name,
    zip_folder,
)
from simcore_service_webserver.exporter.async_hashing import Algorithm
from simcore_service_webserver.exporter.exceptions import ExporterException


@pytest.fixture
def temp_dir(tmpdir) -> Path:
    # cast to Path object
    return Path(tmpdir)


@pytest.fixture
def temp_dir2() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        extract_dir_path = temp_dir_path / "extract_dir"
        extract_dir_path.mkdir(parents=True, exist_ok=True)
        yield extract_dir_path


@pytest.fixture
def temp_file(tmp_path: Path) -> Iterator[Path]:
    file_path = tmp_path / "file"
    file_path.write_text("test_data")
    yield file_path
    file_path.unlink()


@pytest.fixture
def project_uuid():
    return str(uuid.uuid4())


def temp_dir_with_existing_archive(temp_dir, project_uui) -> Path:
    nested_dir = temp_dir / "nested"
    nested_dir.mkdir(parents=True, exist_ok=True)
    nested_file = nested_dir / "archive.zip"
    nested_file.write_text("some_data")

    return nested_dir


def temp_dir_to_compress(temp_dir, project_uuid) -> Path:
    nested_dir = temp_dir / project_uuid
    nested_dir.mkdir(parents=True, exist_ok=True)
    nested_file = nested_dir / "random_file.txt"
    nested_file.write_text("some_data")

    return nested_dir


def temp_dir_to_compress_with_too_many_targets(temp_dir, project_uuid) -> Path:
    nested_dir = temp_dir / project_uuid
    nested_dir.mkdir(parents=True, exist_ok=True)
    nested_file = nested_dir / "random_file.txt"
    nested_file.write_text("some_data")

    extra_dir = temp_dir / "extra"
    extra_dir.mkdir(parents=True, exist_ok=True)

    return nested_dir


def strip_directory_from_path(input_path: Path, to_strip: Path) -> Path:
    _to_strip = f"{str(to_strip)}/"
    return Path(str(input_path).replace(_to_strip, ""))


def get_all_files_in_dir(dir_path: Path) -> set[Path]:
    return {
        strip_directory_from_path(x, dir_path)
        for x in dir_path.rglob("*")
        if x.is_file()
    }


def _compute_hash(file_path: Path) -> tuple[Path, str]:
    with open(file_path, "rb") as file_to_hash:
        file_hash = hashlib.md5()
        chunk = file_to_hash.read(8192)
        while chunk:
            file_hash.update(chunk)
            chunk = file_to_hash.read(8192)

    return file_path, file_hash.hexdigest()


async def compute_hashes(file_paths: list[Path]) -> dict[Path, str]:
    """given a list of files computes hashes for the files on a process pool"""

    loop = asyncio.get_event_loop()

    with ProcessPoolExecutor() as prcess_pool_executor:
        tasks = [
            loop.run_in_executor(prcess_pool_executor, _compute_hash, file_path)
            for file_path in file_paths
        ]
        return dict(await asyncio.gather(*tasks))


def full_file_path_from_dir_and_subdirs(dir_path: Path) -> list[Path]:
    return [x for x in dir_path.rglob("*") if x.is_file()]


async def assert_same_directory_content(
    dir_to_compress: Path, output_dir: Path
) -> None:
    input_set = get_all_files_in_dir(dir_to_compress)
    output_set = get_all_files_in_dir(output_dir)
    assert (
        input_set == output_set
    ), f"There following files are missing {input_set - output_set}"

    # computing the hashes for dir_to_compress and map in a dict
    # with the name starting from the root of the directory and md5sum
    dir_to_compress_hashes = {
        strip_directory_from_path(k, dir_to_compress): v
        for k, v in (
            await compute_hashes(full_file_path_from_dir_and_subdirs(dir_to_compress))
        ).items()
    }

    # computing the hashes for output_dir and map in a dict
    # with the name starting from the root of the directory and md5sum
    output_dir_hashes = {
        strip_directory_from_path(k, output_dir): v
        for k, v in (
            await compute_hashes(full_file_path_from_dir_and_subdirs(output_dir))
        ).items()
    }

    # finally check if hashes are mapped 1 to 1 in order to verify
    # that the compress/decompress worked correctly
    for key in dir_to_compress_hashes:
        assert dir_to_compress_hashes[key] == output_dir_hashes[key]


def test_validate_osparc_file_name_ok():
    algorithm, digest_sum = validate_osparc_import_name(
        "v1#SHA256=80e69a0973e15f4a9c3c180d00a39ee0b0dfafe43356f867983e1180e9b5a892.osparc"
    )

    assert isinstance(algorithm, Algorithm)
    assert (
        digest_sum == "80e69a0973e15f4a9c3c180d00a39ee0b0dfafe43356f867983e1180e9b5a892"
    )


def test_validate_osparc_file_name_no_extention():
    with pytest.raises(ExporterException) as exc_info:
        validate_osparc_import_name(
            "v1#SHA256=80e69a0973e15f4a9c3c180d00a39ee0b0dfafe43356f867983e1180e9b5a892"
        )

    assert exc_info.type is ExporterException
    assert exc_info.value.args[0] == (
        "Provided file name must haave .osparc extension file_name=v1#SHA256="
        "80e69a0973e15f4a9c3c180d00a39ee0b0dfafe43356f867983e1180e9b5a892"
    )


def test_validate_osparc_file_name_more_then_one_extention():
    with pytest.raises(ExporterException) as exc_info:
        validate_osparc_import_name("v1.osparc")

    assert exc_info.type is ExporterException
    assert (
        exc_info.value.args[0]
        == "Could not find a digest in provided file_name=v1.osparc"
    )


def test_validate_osparc_file_name_too_many_shasums():
    with pytest.raises(ExporterException) as exc_info:
        validate_osparc_import_name(
            "v1#SHA256=80e69a0973e15f4a9c3c180d00a39ee0b0dfafe43356f867983e118"
            "0e9b5a892SHA256=80e69a0973e15f4a9c3c180d00a39ee0b0dfafe43356f867983e1180e9b5a892.osparc"
        )

    assert exc_info.type is ExporterException
    assert exc_info.value.args[0] == (
        "Could not find a valid digest in provided file_name=v1#SHA256=80e69a0973e15f"
        "4a9c3c180d00a39ee0b0dfafe43356f867983e1180e9b5a892SHA256=80e69a0973e15f4a9c3c"
        "180d00a39ee0b0dfafe43356f867983e1180e9b5a892.osparc"
    )


async def test_error_during_decompression():
    with pytest.raises(ExporterException) as exc_info:
        await unzip_folder(
            Path("/i/do/not/exist"), Path("/tmp/do_i_not_exist_properly_two")
        )

    assert exc_info.type is ExporterException
    assert exc_info.value.args[0] == (
        "There was an error while extracting '/i/do/not/exist' directory to '/tmp/do_i_not_exist_properly_two'; files_in_destination_directory=[]"
    )


async def test_archive_already_exists(temp_dir, project_uuid):
    tmp_dir_to_compress = temp_dir_with_existing_archive(temp_dir, project_uuid)
    with pytest.raises(ExporterException) as exc_info:
        await zip_folder(
            folder_to_zip=tmp_dir_to_compress, destination_folder=tmp_dir_to_compress
        )

    assert exc_info.type is ExporterException
    assert (
        exc_info.value.args[0]
        == f"Cannot archive '{temp_dir}/nested' because '{str(temp_dir)}/nested/archive.zip' already exists"
    )


async def test_unzip_found_too_many_project_targets(temp_dir, project_uuid):
    tmp_dir_to_compress = temp_dir_to_compress_with_too_many_targets(
        temp_dir, project_uuid
    )

    archive_path = await zip_folder(
        folder_to_zip=tmp_dir_to_compress, destination_folder=tmp_dir_to_compress
    )

    str_archive_path = str(archive_path)

    assert ".osparc" in str_archive_path
    assert "#" in str_archive_path

    os.system(f"rm -rf {str(tmp_dir_to_compress)}")

    with pytest.raises(ExporterException) as exc_info:
        await unzip_folder(archive_path, archive_path.parent)

    assert exc_info.type is ExporterException
    assert exc_info.value.args[0].startswith("There was an error while extracting ")


async def test_same_dir_structure_after_compress_decompress(
    dir_with_random_content: Path, temp_dir2: Path
):
    zip_archive = await zip_folder(
        folder_to_zip=dir_with_random_content,
        destination_folder=dir_with_random_content,
    )

    unzipped_content = await unzip_folder(
        archive_to_extract=zip_archive, destination_folder=temp_dir2
    )
    zip_archive.unlink()
    (unzipped_content.parent / "archive.zip").unlink()

    print(unzipped_content.parent)
    print(dir_with_random_content)
    await assert_same_directory_content(
        dir_with_random_content, unzipped_content.parent
    )
