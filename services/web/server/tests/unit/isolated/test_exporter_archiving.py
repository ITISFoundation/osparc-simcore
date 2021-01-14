# pylint:disable=redefined-outer-name,unused-argument

import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from simcore_service_webserver.exporter.archiving import (
    unzip_folder,
    validate_osparc_import_name,
    zip_folder,
)
from simcore_service_webserver.exporter.async_hashing import Algorithm
from simcore_service_webserver.exporter.exceptions import ExporterException


@pytest.fixture
async def monkey_patch_asyncio_subporcess(loop, mocker):
    # TODO: The below bug is not allowing me to fully test,
    # mocking and waiting for an update
    # https://bugs.python.org/issue35621
    # this issue was patched in 3.8, no need
    if sys.version_info.major == 3 and sys.version_info.minor >= 8:
        raise RuntimeError(
            "Issue no longer present in this version of python, "
            "please remote this mock on python >= 3.8"
        )

    import subprocess

    async def create_subprocess_exec(*command, **extra_params):
        class MockResponse:
            def __init__(self, command, **kwargs):
                self.proc = subprocess.Popen(command, **extra_params)

            async def communicate(self):
                return self.proc.communicate()

            @property
            def returncode(self):
                return self.proc.returncode

        mock_response = MockResponse(command, **extra_params)

        return mock_response

    mocker.patch("asyncio.create_subprocess_exec", side_effect=create_subprocess_exec)


@pytest.fixture
def temp_dir() -> Path:
    with tempfile.TemporaryDirectory() as dir_path:
        yield Path(dir_path)


@pytest.fixture
def temp_file() -> Path:
    file_path = Path("/") / f"tmp/{next(tempfile._get_candidate_names())}"
    file_path.write_text("test_data")
    yield file_path
    file_path.unlink()


@pytest.fixture
def project_uuid():
    return str(uuid.uuid4())


def temp_dir_with_existing_archive(temp_dir, project_uui) -> Path:
    nested_dir = temp_dir / "nested"
    nested_dir.mkdir(parents=True, exist_ok=True)
    nested_file = nested_dir.parent / f"{project_uui}.zip"
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


# end utils


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
            (
                "v1#SHA256=80e69a0973e15f4a9c3c180d00a39ee0b0dfafe43356f867983e118"
                "0e9b5a892SHA256=80e69a0973e15f4a9c3c180d00a39ee0b0dfafe43356f867983e1180e9b5a892.osparc"
            )
        )

    assert exc_info.type is ExporterException
    assert exc_info.value.args[0] == (
        "Could not find a valid digest in provided file_name=v1#SHA256=80e69a0973e15f"
        "4a9c3c180d00a39ee0b0dfafe43356f867983e1180e9b5a892SHA256=80e69a0973e15f4a9c3c"
        "180d00a39ee0b0dfafe43356f867983e1180e9b5a892.osparc"
    )


async def test_error_during_compression(temp_dir, project_uuid):
    with pytest.raises(ExporterException) as exc_info:
        await zip_folder(
            project_id=project_uuid, input_path=temp_dir, no_compression=False
        )

    assert exc_info.type is ExporterException
    assert (
        exc_info.value.args[0]
        == f"[Errno 2] No such file or directory: '{project_uuid}'"
    )


async def test_error_during_decompression():
    with pytest.raises(ExporterException) as exc_info:
        await unzip_folder(Path("/i/do/not/exist"))

    assert exc_info.type is ExporterException
    assert exc_info.value.args[0] == "/i/do/not/exist is not a zip file"


async def test_archive_already_exists(temp_dir, project_uuid):
    tmp_dir_to_compress = temp_dir_with_existing_archive(temp_dir, project_uuid)
    with pytest.raises(ExporterException) as exc_info:
        await zip_folder(
            project_id=project_uuid,
            input_path=tmp_dir_to_compress,
            no_compression=False,
        )

    assert exc_info.type is ExporterException
    assert (
        exc_info.value.args[0]
        == f"Cannot archive because file already exists '{str(temp_dir)}/{project_uuid}.zip'"
    )


@pytest.mark.parametrize("no_compresion", [True, False])
async def test_zip_unzip_folder(
    temp_dir, project_uuid, no_compresion, monkey_patch_asyncio_subporcess
):
    tmp_dir_to_compress = temp_dir_to_compress(temp_dir, project_uuid)
    file_in_archive = tmp_dir_to_compress / "random_file.txt"
    data_before_compression = file_in_archive.read_text()

    archive_path = await zip_folder(
        project_id=project_uuid,
        input_path=tmp_dir_to_compress,
        no_compression=no_compresion,
    )

    str_archive_path = str(archive_path)

    assert ".osparc" in str_archive_path
    assert "#" in str_archive_path

    os.system(f"rm -rf {str(tmp_dir_to_compress)}")

    await unzip_folder(archive_path)

    data_after_decompression = file_in_archive.read_text()

    assert data_before_compression == data_after_decompression


async def test_unzip_found_too_many_project_targets(
    temp_dir, project_uuid, monkey_patch_asyncio_subporcess
):
    tmp_dir_to_compress = temp_dir_to_compress_with_too_many_targets(
        temp_dir, project_uuid
    )

    archive_path = await zip_folder(
        project_id=project_uuid,
        input_path=tmp_dir_to_compress,
        no_compression=False,
    )

    str_archive_path = str(archive_path)

    assert ".osparc" in str_archive_path
    assert "#" in str_archive_path

    os.system(f"rm -rf {str(tmp_dir_to_compress)}")

    with pytest.raises(ExporterException) as exc_info:
        await unzip_folder(archive_path)

    assert exc_info.type is ExporterException
    assert exc_info.value.args[0].startswith(
        "Unexpected number of directories after unzipping"
    )
