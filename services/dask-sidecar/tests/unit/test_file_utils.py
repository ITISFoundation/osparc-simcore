# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterable, cast
from unittest import mock

import fsspec
import pytest
from faker import Faker
from minio import Minio
from pydantic import AnyUrl, parse_obj_as
from pytest_localftpserver.servers import ProcessFTPServer
from pytest_mock.plugin import MockerFixture
from simcore_service_dask_sidecar.file_utils import (
    pull_file_from_remote,
    push_file_to_remote,
)


@pytest.fixture()
async def mocked_log_publishing_cb(
    event_loop: asyncio.AbstractEventLoop,
    mocker: MockerFixture,
) -> AsyncIterable[mock.AsyncMock]:
    async with mocker.AsyncMock() as mocked_callback:
        yield mocked_callback


pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["minio"]


@pytest.fixture
def ftp_storage_kwargs(ftpserver: ProcessFTPServer) -> dict[str, Any]:
    return {}


@pytest.fixture
def s3_storage_kwargs(
    minio_config: dict[str, Any], minio_service: Minio
) -> dict[str, Any]:
    return {
        "key": minio_config["client"]["access_key"],
        "secret": minio_config["client"]["secret_key"],
        "use_ssl": minio_config["client"]["secure"],
        "client_kwargs": {
            "endpoint_url": f"http{'s' if minio_config['client']['secure'] else ''}://{minio_config['client']['endpoint']}"
        },
    }


@pytest.fixture
def ftp_remote_file_url(ftpserver: ProcessFTPServer, faker: Faker) -> AnyUrl:
    return parse_obj_as(
        AnyUrl, f"{ftpserver.get_login_data(style='url')}/{faker.file_name()}"
    )


@pytest.fixture
def s3_remote_file_url(minio_config: dict[str, Any], faker: Faker) -> AnyUrl:
    return parse_obj_as(
        AnyUrl, f"s3://{minio_config['bucket_name']}{faker.file_path()}"
    )


@dataclass
class StorageParameters:
    storage_kwargs: dict[str, Any]
    remote_file_url: AnyUrl


@pytest.fixture(params=["ftp", "s3"])
def remote_parameters(
    request: pytest.FixtureRequest,
    ftp_remote_file_url: AnyUrl,
    s3_remote_file_url: AnyUrl,
    ftp_storage_kwargs: dict[str, Any],
    s3_storage_kwargs: dict[str, Any],
) -> StorageParameters:
    return {
        "ftp": StorageParameters(
            storage_kwargs=ftp_storage_kwargs, remote_file_url=ftp_remote_file_url
        ),
        "s3": StorageParameters(
            storage_kwargs=s3_storage_kwargs, remote_file_url=s3_remote_file_url
        ),
    }[request.param]


async def test_copy_file_to_remote(
    remote_parameters: StorageParameters,
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    # let's create some file with text inside
    src_path = tmp_path / faker.file_name()
    TEXT_IN_FILE = faker.text()
    src_path.write_text(TEXT_IN_FILE)
    assert src_path.exists()
    # push it to the remote
    await push_file_to_remote(
        src_path,
        remote_parameters.remote_file_url,
        mocked_log_publishing_cb,
        **remote_parameters.storage_kwargs,
    )

    # check the remote is actually having the file in
    open_file = cast(
        fsspec.core.OpenFile,
        fsspec.open(
            remote_parameters.remote_file_url,
            mode="rt",
            **remote_parameters.storage_kwargs,
        ),
    )
    with open_file as fp:
        assert fp.read() == TEXT_IN_FILE
    mocked_log_publishing_cb.assert_called()


async def test_copy_file_to_remote_compresses_if_zip_destination(
    remote_parameters: StorageParameters,
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    destination_url = parse_obj_as(AnyUrl, f"{remote_parameters.remote_file_url}.zip")
    src_path = tmp_path / faker.file_name()
    TEXT_IN_FILE = faker.text()
    src_path.write_text(TEXT_IN_FILE)
    assert src_path.exists()

    await push_file_to_remote(
        src_path,
        destination_url,
        mocked_log_publishing_cb,
        **remote_parameters.storage_kwargs,
    )

    open_files = fsspec.open_files(
        f"zip://*::{destination_url}",
        mode="rt",
        **{destination_url.scheme: remote_parameters.storage_kwargs},
    )
    assert len(open_files) == 1
    with open_files[0] as fp:
        assert fp.read() == TEXT_IN_FILE
    mocked_log_publishing_cb.assert_called()


async def test_pull_file_from_remote(
    ftpserver: ProcessFTPServer,
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    ftp_server = cast(dict, ftpserver.get_login_data())
    ftp_server["password"] = ftp_server["passwd"]
    del ftp_server["passwd"]
    ftp_server["username"] = ftp_server["user"]
    del ftp_server["user"]

    # put some file on the remote
    fs = fsspec.filesystem("ftp", **ftp_server)
    TEXT_IN_FILE = faker.text()
    file_name = faker.file_name()
    with fs.open(file_name, mode="wt") as fp:
        fp.write(TEXT_IN_FILE)

    ftp_server_url_login_data = ftpserver.get_login_data(style="url")

    src_url = parse_obj_as(AnyUrl, f"{ftp_server_url_login_data}/{file_name}")
    dst_path = tmp_path / faker.file_name()
    await pull_file_from_remote(src_url, dst_path, mocked_log_publishing_cb)
    assert dst_path.exists()
    assert dst_path.read_text() == TEXT_IN_FILE
    mocked_log_publishing_cb.assert_called()


async def test_pull_compressed_zip_file_from_remote(
    ftpserver: ProcessFTPServer,
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    ftp_server = cast(dict, ftpserver.get_login_data())
    ftp_server["password"] = ftp_server["passwd"]
    del ftp_server["passwd"]
    ftp_server["username"] = ftp_server["user"]
    del ftp_server["user"]

    # put some zip file on the remote
    local_zip_file_path = tmp_path / f"{faker.file_name()}.zip"
    local_test_file = tmp_path / faker.file_name()
    local_test_file.write_text(faker.text())
    assert local_test_file.exists()
    with zipfile.ZipFile(
        local_zip_file_path, compression=zipfile.ZIP_DEFLATED, mode="w"
    ) as zfp:
        zfp.write(local_test_file, local_test_file.name)

    ftp_zip_file_path = f"{faker.file_name()}.zip"
    fs = fsspec.filesystem("ftp", **ftp_server)
    fs.put_file(local_zip_file_path, ftp_zip_file_path)
    assert fs.exists(ftp_zip_file_path)

    # USE-CASE 1: if destination is a zip then no decompression is done
    ftp_server_url_login_data = ftpserver.get_login_data(style="url")

    src_url = parse_obj_as(AnyUrl, f"{ftp_server_url_login_data}/{ftp_zip_file_path}")
    download_folder = tmp_path / "download"
    download_folder.mkdir(parents=True, exist_ok=True)
    assert download_folder.exists()
    dst_path = download_folder / f"{faker.file_name()}.zip"
    await pull_file_from_remote(src_url, dst_path, mocked_log_publishing_cb)
    assert dst_path.exists()
    dst_path.unlink()
    mocked_log_publishing_cb.assert_called()
    mocked_log_publishing_cb.reset_mock()

    # USE-CASE 2: if destination is not a zip, then we decompress
    assert download_folder.exists()
    dst_path = download_folder / faker.file_name()
    await pull_file_from_remote(src_url, dst_path, mocked_log_publishing_cb)
    assert not dst_path.exists()
    expected_download_file_path = download_folder / local_test_file.name
    assert expected_download_file_path.exists()
    mocked_log_publishing_cb.assert_called()
