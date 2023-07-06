# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import time
from pathlib import Path
from uuid import UUID

import osparc
import pytest


def test_upload_file(files_api: osparc.FilesApi, tmp_path: Path):
    input_path = tmp_path / "some-text-file.txt"
    input_path.write_text("demo")

    input_file: osparc.File = files_api.upload_file(file=input_path)
    assert isinstance(input_file, osparc.File)
    time.sleep(2)  # let time to upload to S3

    assert UUID(input_file.id), "Valid uuid ir required"
    assert input_file.filename == input_path.name

    # these two are EXPERIMENTAL. Not reliable!
    assert input_file.content_type is None or input_file.content_type == "text/plain"
    assert input_file.checksum is None or isinstance(input_file.checksum, str)

    same_file = files_api.get_file(input_file.id)
    assert same_file == input_file

    # FIXME: for some reason, S3 takes produces different etags
    # for the same file. Are we changing some bytes in the
    # intermediate upload? Would it work the same avoiding that step
    # and doing direct upload?
    same_file = files_api.upload_file(file=input_path)
    # FIXME: assert input_file.checksum == same_file.checksum


@pytest.mark.parametrize("file_type", ["binary", "text"])
def test_upload_list_and_download(
    files_api: osparc.FilesApi, tmp_path: Path, file_type: str, faker
):
    input_path = tmp_path / (file_type + ".bin" if file_type == "binary" else ".txt")

    if file_type == "text":
        content = faker.text(max_nb_chars=20)
        input_path.write_text(content)
    else:
        content = b"\x01" * 1024
        input_path.write_bytes(content)

    input_file: osparc.File = files_api.upload_file(file=input_path)
    assert isinstance(input_file, osparc.File)
    time.sleep(2)  # let time to upload to S3 ??? <-- WHY???

    assert input_file.filename == input_path.name

    myfiles = files_api.list_files()
    assert myfiles
    assert all(isinstance(f, osparc.File) for f in myfiles)
    assert input_file in myfiles

    download_path: str = files_api.download_file(file_id=input_file.id)

    if file_type == "text":
        assert content == Path(download_path).read_text()
    else:
        assert content == Path(download_path).read_bytes()
