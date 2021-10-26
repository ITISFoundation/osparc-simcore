from pathlib import Path

import fsspec
from pydantic import AnyUrl, parse_obj_as
from pytest_localftpserver.servers import ProcessFTPServer
from simcore_service_dask_sidecar.file_utils import copy_file_to_remote


async def test_copy_file_to_remote(ftpserver: ProcessFTPServer, tmp_path: Path):
    ftp_server_base_url = ftpserver.get_login_data(style="url")

    file_on_remote = f"{ftp_server_base_url}/some_remote_filename"
    destination_url = parse_obj_as(AnyUrl, file_on_remote)
    src_path = tmp_path / "some_file"
    TEXT_IN_FILE = "This is some test data in the file"
    src_path.write_text(TEXT_IN_FILE)
    assert src_path.exists()

    await copy_file_to_remote(src_path, destination_url)

    open_file = fsspec.open(destination_url, mode="rt")
    with open_file as fp:
        assert fp.read() == TEXT_IN_FILE


async def test_copy_file_to_remote_compresses_if_zip_destination(
    ftpserver: ProcessFTPServer, tmp_path: Path
):
    ftp_server_base_url = ftpserver.get_login_data(style="url")

    file_on_remote = f"{ftp_server_base_url}/some_remote_zip_filename.zip"
    destination_url = parse_obj_as(AnyUrl, file_on_remote)
    src_path = tmp_path / "some_file"
    TEXT_IN_FILE = "This is some test data in the file"
    src_path.write_text(TEXT_IN_FILE)
    assert src_path.exists()

    await copy_file_to_remote(src_path, destination_url)

    # fsspec.filesystem("zip", destination_url)

    open_files = fsspec.open_files(f"zip://*::{destination_url}", mode="rt")
    assert len(open_files) == 1
    with open_files[0] as fp:
        assert fp.read() == TEXT_IN_FILE
