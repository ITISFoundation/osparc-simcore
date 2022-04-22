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
from _pytest.fixtures import FixtureRequest
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
def s3_presigned_link_storage_kwargs(
    minio_config: dict[str, Any], minio_service: Minio
) -> dict[str, Any]:
    return {}


@pytest.fixture
def s3_endpoint_url(minio_config: dict[str, Any]) -> AnyUrl:
    return parse_obj_as(
        AnyUrl,
        f"http{'s' if minio_config['client']['secure'] else ''}://{minio_config['client']['endpoint']}",
    )


@pytest.fixture
def s3_storage_kwargs(
    minio_config: dict[str, Any], minio_service: Minio, s3_endpoint_url: AnyUrl
) -> dict[str, Any]:
    return {
        "key": minio_config["client"]["access_key"],
        "secret": minio_config["client"]["secret_key"],
        "use_ssl": minio_config["client"]["secure"],
        "client_kwargs": {"endpoint_url": f"{s3_endpoint_url}"},
    }


@pytest.fixture
def ftp_remote_file_url(ftpserver: ProcessFTPServer, faker: Faker) -> AnyUrl:
    return parse_obj_as(
        AnyUrl, f"{ftpserver.get_login_data(style='url')}/{faker.file_name()}"
    )


@pytest.fixture
def s3_presigned_link_remote_file_url(
    minio_config: dict[str, Any],
    minio_service: Minio,
    faker: Faker,
) -> AnyUrl:

    return parse_obj_as(
        AnyUrl,
        minio_service.presigned_put_object(
            minio_config["bucket_name"], faker.file_name()
        ),
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
    request: FixtureRequest,
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
    }[
        request.param  # type: ignore
    ]


async def test_push_file_to_remote(
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


async def test_push_file_to_remote_s3_http_presigned_link(
    s3_presigned_link_remote_file_url: AnyUrl,
    s3_storage_kwargs: dict[str, Any],
    minio_config: dict[str, Any],
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
        s3_presigned_link_remote_file_url,
        mocked_log_publishing_cb,
    )

    # check the remote is actually having the file in, but we need s3 access now
    s3_remote_file_url = parse_obj_as(
        AnyUrl,
        f"s3:/{s3_presigned_link_remote_file_url.path}",
    )
    open_file = cast(
        fsspec.core.OpenFile,
        fsspec.open(s3_remote_file_url, mode="rt", **s3_storage_kwargs),
    )
    with open_file as fp:
        assert fp.read() == TEXT_IN_FILE
    mocked_log_publishing_cb.assert_called()


async def test_push_file_to_remote_compresses_if_zip_destination(
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
        assert fp.read() == TEXT_IN_FILE  # type: ignore
    mocked_log_publishing_cb.assert_called()


async def test_pull_file_from_remote(
    remote_parameters: StorageParameters,
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    # put some file on the remote
    open_file = cast(
        fsspec.core.OpenFile,
        fsspec.open(
            remote_parameters.remote_file_url,
            mode="wt",
            **remote_parameters.storage_kwargs,
        ),
    )
    TEXT_IN_FILE = faker.text()
    with open_file as fp:
        fp.write(TEXT_IN_FILE)

    # now let's get the file through the util
    dst_path = tmp_path / faker.file_name()
    await pull_file_from_remote(
        remote_parameters.remote_file_url,
        dst_path,
        mocked_log_publishing_cb,
        **remote_parameters.storage_kwargs,
    )
    assert dst_path.exists()
    assert dst_path.read_text() == TEXT_IN_FILE
    mocked_log_publishing_cb.assert_called()


async def test_pull_file_from_remote_s3_presigned_link(
    s3_storage_kwargs: dict[str, Any],
    s3_remote_file_url: AnyUrl,
    minio_service: Minio,
    minio_config: dict[str, Any],
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    # put some file on the remote
    open_file = cast(
        fsspec.core.OpenFile,
        fsspec.open(
            s3_remote_file_url,
            mode="wt",
            **s3_storage_kwargs,
        ),
    )
    TEXT_IN_FILE = faker.text()
    with open_file as fp:
        fp.write(TEXT_IN_FILE)

    # create a corresponding presigned get link
    assert s3_remote_file_url.path
    remote_file_url = parse_obj_as(
        AnyUrl,
        minio_service.presigned_get_object(
            minio_config["bucket_name"],
            s3_remote_file_url.path.removeprefix(f"/{minio_config['bucket_name']}/"),
        ),
    )
    # now let's get the file through the util
    dst_path = tmp_path / faker.file_name()
    await pull_file_from_remote(
        remote_file_url,
        dst_path,
        mocked_log_publishing_cb,
    )
    assert dst_path.exists()
    assert dst_path.read_text() == TEXT_IN_FILE
    mocked_log_publishing_cb.assert_called()


async def test_pull_compressed_zip_file_from_remote(
    remote_parameters: StorageParameters,
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    # put some zip file on the remote
    local_zip_file_path = tmp_path / f"{faker.file_name()}.zip"
    file_names_within_zip_file = set()
    with zipfile.ZipFile(
        local_zip_file_path, compression=zipfile.ZIP_DEFLATED, mode="w"
    ) as zfp:
        for file_number in range(5):
            local_test_file = tmp_path / f"{file_number}_{faker.file_name()}"
            local_test_file.write_text(faker.text())
            assert local_test_file.exists()
            zfp.write(local_test_file, local_test_file.name)
            file_names_within_zip_file.add(local_test_file.name)

    destination_url = parse_obj_as(AnyUrl, f"{remote_parameters.remote_file_url}.zip")
    open_file = cast(
        fsspec.core.OpenFile,
        fsspec.open(
            destination_url,
            mode="wb",
            **remote_parameters.storage_kwargs,
        ),
    )

    with open_file as dest_fp:
        with local_zip_file_path.open("rb") as src_fp:
            dest_fp.write(src_fp.read())

    # now we want to download that file so it becomes the source
    src_url = destination_url

    # USE-CASE 1: if destination is a zip then no decompression is done
    download_folder = tmp_path / "download"
    download_folder.mkdir(parents=True, exist_ok=True)
    assert download_folder.exists()
    dst_path = download_folder / f"{faker.file_name()}.zip"

    await pull_file_from_remote(
        src_url, dst_path, mocked_log_publishing_cb, **remote_parameters.storage_kwargs
    )
    assert dst_path.exists()
    dst_path.unlink()
    mocked_log_publishing_cb.assert_called()
    mocked_log_publishing_cb.reset_mock()

    # USE-CASE 2: if destination is not a zip, then we decompress
    assert download_folder.exists()
    dst_path = download_folder / faker.file_name()
    await pull_file_from_remote(
        src_url, dst_path, mocked_log_publishing_cb, **remote_parameters.storage_kwargs
    )
    assert not dst_path.exists()
    for file in download_folder.glob("*"):
        assert file.exists()
        assert file.name in file_names_within_zip_file
    mocked_log_publishing_cb.assert_called()
