# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import hashlib
import mimetypes
import zipfile
from collections.abc import AsyncIterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from unittest import mock

import fsspec
import pytest
from faker import Faker
from pydantic import AnyUrl, TypeAdapter
from pytest_localftpserver.servers import ProcessFTPServer
from pytest_mock.plugin import MockerFixture
from settings_library.s3 import S3Settings
from simcore_service_dask_sidecar.file_utils import (
    _s3fs_settings_from_s3_settings,
    pull_file_from_remote,
    push_file_to_remote,
)


@pytest.fixture()
async def mocked_log_publishing_cb(
    mocker: MockerFixture,
) -> AsyncIterable[mock.AsyncMock]:
    async with mocker.AsyncMock() as mocked_callback:
        yield mocked_callback


pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def s3_presigned_link_storage_kwargs(s3_settings: S3Settings) -> dict[str, Any]:
    return {}


@pytest.fixture
def ftp_remote_file_url(ftpserver: ProcessFTPServer, faker: Faker) -> AnyUrl:
    return TypeAdapter(AnyUrl).validate_python(
        f"{ftpserver.get_login_data(style='url')}/{faker.file_name()}"
    )


@pytest.fixture
async def s3_presigned_link_remote_file_url(
    s3_settings: S3Settings,
    aiobotocore_s3_client,
    faker: Faker,
) -> AnyUrl:
    return TypeAdapter(AnyUrl).validate_python(
        await aiobotocore_s3_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": s3_settings.S3_BUCKET_NAME, "Key": faker.file_name()},
            ExpiresIn=30,
        ),
    )


@pytest.fixture
def s3_remote_file_url(s3_settings: S3Settings, faker: Faker) -> AnyUrl:
    return TypeAdapter(AnyUrl).validate_python(
        f"s3://{s3_settings.S3_BUCKET_NAME}{faker.file_path()}"
    )


@dataclass(frozen=True)
class StorageParameters:
    s3_settings: S3Settings | None
    remote_file_url: AnyUrl


@pytest.fixture(params=["ftp", "s3"])
def remote_parameters(
    request: pytest.FixtureRequest,
    ftp_remote_file_url: AnyUrl,
    s3_remote_file_url: AnyUrl,
    s3_settings: S3Settings,
) -> StorageParameters:
    return {
        "ftp": StorageParameters(s3_settings=None, remote_file_url=ftp_remote_file_url),
        "s3": StorageParameters(
            s3_settings=s3_settings, remote_file_url=s3_remote_file_url
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
        remote_parameters.s3_settings,
    )

    # check the remote is actually having the file in
    storage_kwargs = {}
    if remote_parameters.s3_settings:
        storage_kwargs = _s3fs_settings_from_s3_settings(remote_parameters.s3_settings)

    with cast(
        fsspec.core.OpenFile,
        fsspec.open(
            f"{remote_parameters.remote_file_url}",
            mode="rt",
            **storage_kwargs,
        ),
    ) as fp:
        assert fp.read() == TEXT_IN_FILE
    mocked_log_publishing_cb.assert_called()


async def test_push_file_to_remote_s3_http_presigned_link(
    s3_presigned_link_remote_file_url: AnyUrl,
    s3_settings: S3Settings,
    bucket: str,
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
        s3_settings=None,
    )

    # check the remote is actually having the file in, but we need s3 access now
    s3_remote_file_url = TypeAdapter(AnyUrl).validate_python(
        f"s3:/{s3_presigned_link_remote_file_url.path}",
    )

    storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)
    with cast(
        fsspec.core.OpenFile,
        fsspec.open(f"{s3_remote_file_url}", mode="rt", **storage_kwargs),
    ) as fp:
        assert fp.read() == TEXT_IN_FILE
    mocked_log_publishing_cb.assert_called()


async def test_push_file_to_remote_compresses_if_zip_destination(
    remote_parameters: StorageParameters,
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    destination_url = TypeAdapter(AnyUrl).validate_python(
        f"{remote_parameters.remote_file_url}.zip"
    )
    src_path = tmp_path / faker.file_name()
    TEXT_IN_FILE = faker.text()
    src_path.write_text(TEXT_IN_FILE)
    assert src_path.exists()

    await push_file_to_remote(
        src_path,
        destination_url,
        mocked_log_publishing_cb,
        remote_parameters.s3_settings,
    )

    storage_kwargs = {}
    if remote_parameters.s3_settings:
        storage_kwargs = _s3fs_settings_from_s3_settings(remote_parameters.s3_settings)
    open_files = fsspec.open_files(
        f"zip://*::{destination_url}",
        mode="rt",
        **{destination_url.scheme: storage_kwargs},
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
    storage_kwargs = {}
    if remote_parameters.s3_settings:
        storage_kwargs = _s3fs_settings_from_s3_settings(remote_parameters.s3_settings)
    # put some file on the remote
    TEXT_IN_FILE = faker.text()
    with cast(
        fsspec.core.OpenFile,
        fsspec.open(
            f"{remote_parameters.remote_file_url}",
            mode="wt",
            **storage_kwargs,
        ),
    ) as fp:
        fp.write(TEXT_IN_FILE)

    # now let's get the file through the util
    dst_path = tmp_path / faker.file_name()
    await pull_file_from_remote(
        src_url=remote_parameters.remote_file_url,
        target_mime_type=None,
        dst_path=dst_path,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
    )
    assert dst_path.exists()
    assert dst_path.read_text() == TEXT_IN_FILE
    mocked_log_publishing_cb.assert_called()


async def test_pull_file_from_remote_s3_presigned_link(
    s3_settings: S3Settings,
    s3_remote_file_url: AnyUrl,
    aiobotocore_s3_client,
    bucket: str,
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)
    # put some file on the remote
    TEXT_IN_FILE = faker.text()
    with cast(
        fsspec.core.OpenFile,
        fsspec.open(
            f"{s3_remote_file_url}",
            mode="wt",
            **storage_kwargs,
        ),
    ) as fp:
        fp.write(TEXT_IN_FILE)

    # create a corresponding presigned get link
    assert s3_remote_file_url.path
    remote_file_url = TypeAdapter(AnyUrl).validate_python(
        await aiobotocore_s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": s3_settings.S3_BUCKET_NAME,
                "Key": s3_remote_file_url.path.removeprefix("/"),
            },
            ExpiresIn=30,
        ),
    )
    # now let's get the file through the util
    dst_path = tmp_path / faker.file_name()
    await pull_file_from_remote(
        src_url=remote_file_url,
        target_mime_type=None,
        dst_path=dst_path,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=None,
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

    destination_url = TypeAdapter(AnyUrl).validate_python(
        f"{remote_parameters.remote_file_url}.zip"
    )
    storage_kwargs = {}
    if remote_parameters.s3_settings:
        storage_kwargs = _s3fs_settings_from_s3_settings(remote_parameters.s3_settings)

    with cast(
        fsspec.core.OpenFile,
        fsspec.open(
            f"{destination_url}",
            mode="wb",
            **storage_kwargs,
        ),
    ) as dest_fp, local_zip_file_path.open("rb") as src_fp:
        dest_fp.write(src_fp.read())

    # now we want to download that file so it becomes the source
    src_url = destination_url

    # USE-CASE 1: if destination is a zip then no decompression is done
    download_folder = tmp_path / "download"
    download_folder.mkdir(parents=True, exist_ok=True)
    assert download_folder.exists()
    dst_path = download_folder / f"{faker.file_name()}.zip"

    await pull_file_from_remote(
        src_url=src_url,
        target_mime_type=None,
        dst_path=dst_path,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
    )
    assert dst_path.exists()
    dst_path.unlink()
    mocked_log_publishing_cb.assert_called()
    mocked_log_publishing_cb.reset_mock()

    # USE-CASE 2: if destination is not a zip, then we decompress
    assert download_folder.exists()
    dst_path = download_folder / faker.file_name()
    await pull_file_from_remote(
        src_url=src_url,
        target_mime_type=None,
        dst_path=dst_path,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
    )
    assert not dst_path.exists()
    for file in download_folder.glob("*"):
        assert file.exists()
        assert file.name in file_names_within_zip_file
    mocked_log_publishing_cb.assert_called()
    mocked_log_publishing_cb.reset_mock()

    # USE-CASE 3: if destination is a zip, but we pass a target mime type that is not, then we decompress
    download_folder = tmp_path / "download2"
    download_folder.mkdir(parents=True, exist_ok=True)
    assert download_folder.exists()
    dst_path = download_folder / f"{faker.file_name()}.zip"
    mime_type, _ = mimetypes.guess_type(
        faker.file_name()
    )  # let's have a standard mime type
    await pull_file_from_remote(
        src_url=src_url,
        target_mime_type=mime_type,
        dst_path=dst_path,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
    )
    assert not dst_path.exists()
    for file in download_folder.glob("*"):
        assert file.exists()
        assert file.name in file_names_within_zip_file
    mocked_log_publishing_cb.assert_called()


def _compute_hash(file_path: Path) -> str:
    with file_path.open("rb") as file_to_hash:
        file_hash = hashlib.sha256()
        chunk = file_to_hash.read(8192)
        while chunk:
            file_hash.update(chunk)
            chunk = file_to_hash.read(8192)

    return file_hash.hexdigest()


async def test_push_file_to_remote_creates_reproducible_zip_archive(
    remote_parameters: StorageParameters,
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    destination_url1 = TypeAdapter(AnyUrl).validate_python(
        f"{remote_parameters.remote_file_url}1.zip"
    )
    destination_url2 = TypeAdapter(AnyUrl).validate_python(
        f"{remote_parameters.remote_file_url}2.zip"
    )
    src_path = tmp_path / faker.file_name()
    TEXT_IN_FILE = faker.text()
    src_path.write_text(TEXT_IN_FILE)
    assert src_path.exists()

    # pushing 2 times should produce the same archive with the same hash
    await push_file_to_remote(
        src_path,
        destination_url1,
        mocked_log_publishing_cb,
        remote_parameters.s3_settings,
    )
    await asyncio.sleep(
        5
    )  # NOTE: we wait a bit to ensure the created zipfile has a different creation time (that is normally used for computing the hash)
    await push_file_to_remote(
        src_path,
        destination_url2,
        mocked_log_publishing_cb,
        remote_parameters.s3_settings,
    )

    # now we pull both file and compare their hash

    # USE-CASE 1: if destination is a zip then no decompression is done
    download_folder = tmp_path / "download"
    download_folder.mkdir(parents=True, exist_ok=True)
    assert download_folder.exists()
    dst_path1 = download_folder / f"{faker.file_name()}1.zip"
    dst_path2 = download_folder / f"{faker.file_name()}2.zip"

    await pull_file_from_remote(
        src_url=destination_url1,
        target_mime_type=None,
        dst_path=dst_path1,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
    )
    assert dst_path1.exists()

    await pull_file_from_remote(
        src_url=destination_url2,
        target_mime_type=None,
        dst_path=dst_path2,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
    )
    assert dst_path2.exists()

    assert _compute_hash(dst_path1) == _compute_hash(dst_path2)
