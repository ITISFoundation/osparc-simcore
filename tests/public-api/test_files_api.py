# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import time
from pathlib import Path

import osparc
import pytest
from osparc.api.files_api import FilesApi
from osparc.models import FileMetadata


@pytest.fixture()
def files_api(api_client):
    return FilesApi(api_client)


def test_upload_file(files_api: FilesApi, tmpdir):
    input_path = Path(tmpdir) / "some-text-file.txt"
    input_path.write_text("demo")

    input_file: FileMetadata = files_api.upload_file(file=input_path)
    assert isinstance(input_file, FileMetadata)
    time.sleep(2)  # let time to upload to S3

    assert input_file.filename == input_path.name
    assert input_file.content_type == "text/plain"

    same_file = files_api.get_file(input_file.file_id)
    assert same_file == input_file

    # FIXME: for some reason, S3 takes produces different etags
    # for the same file. Are we changing some bytes in the
    # intermediate upload? Would it work the same avoiding that step
    # and doing direct upload?
    same_file = files_api.upload_file(file=input_path)
    # FIXME: assert input_file.checksum == same_file.checksum


def test_upload_list_and_download(files_api: FilesApi, tmpdir):
    input_path = Path(tmpdir) / "some-hdf5-file.h5"
    input_path.write_bytes(b"demo but some other stuff as well")

    input_file: FileMetadata = files_api.upload_file(file=input_path)
    assert isinstance(input_file, FileMetadata)
    time.sleep(2)  # let time to upload to S3

    assert input_file.filename == input_path.name

    myfiles = files_api.list_files()
    assert myfiles
    assert all(isinstance(f, FileMetadata) for f in myfiles)
    assert input_file in myfiles

    # FIXME: does not download actually the file but text ...
    # ('--e66c24aef3a840f024407d17ba9046a8\r\n'\n 'Content-Disposition: form-data; name="upload-file"; '\n 'filename="some-hdf5-file.h5"\r\n'\n 'Content-Type: application/octet-stream\r\n'\n '\r\n'\n 'demo but some other stuff as well\r\n'\n '--e66c24aef3a840f024407d17ba9046a8--\r\n')
    same_file = files_api.download_file(file_id=input_file.file_id)
    assert input_path.read_text() == same_file
    # TODO: check response of dowload_file ... says json
