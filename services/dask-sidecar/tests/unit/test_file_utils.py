import zipfile
from pathlib import Path
from typing import cast

import fsspec
from pydantic import AnyUrl, parse_obj_as
from pytest_localftpserver.servers import ProcessFTPServer
from simcore_service_dask_sidecar.file_utils import (
    pull_file_from_remote,
    push_file_to_remote,
)


async def test_copy_file_to_remote(ftpserver: ProcessFTPServer, tmp_path: Path):
    ftp_server_base_url = ftpserver.get_login_data(style="url")

    file_on_remote = f"{ftp_server_base_url}/some_remote_filename"
    destination_url = parse_obj_as(AnyUrl, file_on_remote)
    src_path = tmp_path / "some_file"
    TEXT_IN_FILE = "This is some test data in the file"
    src_path.write_text(TEXT_IN_FILE)
    assert src_path.exists()

    await push_file_to_remote(src_path, destination_url)

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

    await push_file_to_remote(src_path, destination_url)

    open_files = fsspec.open_files(f"zip://*::{destination_url}", mode="rt")
    assert len(open_files) == 1
    with open_files[0] as fp:
        assert fp.read() == TEXT_IN_FILE


async def test_pull_file_from_remote(ftpserver: ProcessFTPServer, tmp_path: Path):
    ftp_server = cast(dict, ftpserver.get_login_data())
    ftp_server["password"] = ftp_server["passwd"]
    del ftp_server["passwd"]
    ftp_server["username"] = ftp_server["user"]
    del ftp_server["user"]

    # put some file on the remote
    fs = fsspec.filesystem("ftp", **ftp_server)
    with fs.open("some_normal_file", mode="wt") as fp:
        fp.write("Hello world normal file!")

    ftp_server_url_login_data = ftpserver.get_login_data(style="url")

    src_url = parse_obj_as(AnyUrl, f"{ftp_server_url_login_data}/some_normal_file")
    dst_path = tmp_path / "pulled_file"
    await pull_file_from_remote(src_url, dst_path)
    assert dst_path.exists()
    assert dst_path.read_text() == "Hello world normal file!"


async def test_pull_compressed_zip_file_from_remote(
    ftpserver: ProcessFTPServer, tmp_path: Path
):
    ftp_server = cast(dict, ftpserver.get_login_data())
    ftp_server["password"] = ftp_server["passwd"]
    del ftp_server["passwd"]
    ftp_server["username"] = ftp_server["user"]
    del ftp_server["user"]

    # put some zip file on the remote
    local_zip_file_path = tmp_path / "my_test_zip.zip"
    local_test_file = tmp_path / "my_test_text_file"
    local_test_file.write_text("Hello world normal file!")
    assert local_test_file.exists()
    with zipfile.ZipFile(
        local_zip_file_path, compression=zipfile.ZIP_DEFLATED, mode="w"
    ) as zfp:
        zfp.write(local_test_file, local_test_file.name)

    ftp_zip_file_path = "my_zip.zip"
    fs = fsspec.filesystem("ftp", **ftp_server)
    fs.put_file(local_zip_file_path, ftp_zip_file_path)
    assert fs.exists(ftp_zip_file_path)

    # USE-CASE 1: if destination is a zip then no decompression is done
    ftp_server_url_login_data = ftpserver.get_login_data(style="url")

    src_url = parse_obj_as(AnyUrl, f"{ftp_server_url_login_data}/{ftp_zip_file_path}")
    download_folder = tmp_path / "download"
    download_folder.mkdir(parents=True, exist_ok=True)
    assert download_folder.exists()
    dst_path = download_folder / "pulled_file.zip"
    await pull_file_from_remote(src_url, dst_path)
    assert dst_path.exists()
    dst_path.unlink()

    # USE-CASE 2: if destination is not a zip, then we decompress
    assert download_folder.exists()
    dst_path = download_folder / "pulled_file"
    await pull_file_from_remote(src_url, dst_path)
    assert not dst_path.exists()
    expected_download_file_path = download_folder / "my_test_text_file"
    assert expected_download_file_path.exists()
