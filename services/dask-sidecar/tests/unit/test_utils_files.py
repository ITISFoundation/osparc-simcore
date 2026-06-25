# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import contextlib
import hashlib
import mimetypes
import zipfile
from collections.abc import AsyncIterable, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from unittest import mock

import fsspec
import pytest
from dask_task_models_library.container_tasks.encryption import (
    TransferEncryptionSettings,
)
from faker import Faker
from pydantic import AnyUrl, SecretBytes, TypeAdapter
from pytest_localftpserver.servers import ProcessFTPServer
from pytest_mock.plugin import MockerFixture
from settings_library.s3 import S3Settings
from simcore_service_dask_sidecar.aes_gcm import FORMAT_MAGIC, AesGcmStreamAuthError, generate_key
from simcore_service_dask_sidecar.errors import HTTPDestinationEncryptionNotSupportedError
from simcore_service_dask_sidecar.utils.files import (
    _s3fs_settings_from_s3_settings,
    pull_file_from_remote,
    push_file_to_remote,
)
from types_aiobotocore_s3 import S3Client


@pytest.fixture()
async def mocked_log_publishing_cb(
    mocker: MockerFixture,
) -> AsyncIterable[mock.AsyncMock]:
    async with mocker.AsyncMock() as mocked_callback:
        yield mocked_callback


pytest_simcore_core_services_selection = ["rabbit"]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def s3_presigned_link_storage_kwargs(s3_settings: S3Settings) -> dict[str, Any]:
    return {}


@pytest.fixture
def ftp_remote_file_url(ftpserver: ProcessFTPServer, faker: Faker) -> AnyUrl:
    return TypeAdapter(AnyUrl).validate_python(f"{ftpserver.get_login_data(style='url')}/{faker.file_name()}")


@pytest.fixture
async def s3_presigned_link_remote_file_url(
    s3_settings: S3Settings,
    s3_client: S3Client,
    faker: Faker,
) -> AnyUrl:
    return TypeAdapter(AnyUrl).validate_python(
        await s3_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": s3_settings.S3_BUCKET_NAME, "Key": faker.file_name()},
            ExpiresIn=30,
        ),
    )


@pytest.fixture
def s3_remote_file_url(s3_settings: S3Settings, faker: Faker) -> AnyUrl:
    return TypeAdapter(AnyUrl).validate_python(f"s3://{s3_settings.S3_BUCKET_NAME}{faker.file_path()}")


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
        "s3": StorageParameters(s3_settings=s3_settings, remote_file_url=s3_remote_file_url),
    }[
        request.param  # type: ignore
    ]


@pytest.fixture
def upload_file_to_remote(
    remote_parameters: StorageParameters,
) -> Iterator[Callable[[Path, AnyUrl], None]]:
    storage_kwargs = {}
    if remote_parameters.s3_settings:
        storage_kwargs = cast(dict, _s3fs_settings_from_s3_settings(remote_parameters.s3_settings))

    uploaded_files: list[fsspec.core.OpenFile] = []

    def _upload(local_path: Path, remote_url: AnyUrl) -> None:
        open_file = cast(
            fsspec.core.OpenFile,
            fsspec.open(f"{remote_url}", mode="wb", **storage_kwargs),
        )
        with open_file as dest_fp, local_path.open("rb") as src_fp:
            dest_fp.write(src_fp.read())
        uploaded_files.append(open_file)

    yield _upload

    for open_file in uploaded_files:
        with contextlib.suppress(Exception):
            open_file.fs.rm(open_file.path)


def encryption_settings() -> TransferEncryptionSettings:
    return TransferEncryptionSettings(
        job_key=TypeAdapter(SecretBytes).validate_python(generate_key()),
        job_id="job-1",
        file_id="file-1",
        file_role="input",
    )


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
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
        encryption=None,
    )

    # check the remote is actually having the file in
    storage_kwargs = {}
    if remote_parameters.s3_settings:
        storage_kwargs = cast(dict, _s3fs_settings_from_s3_settings(remote_parameters.s3_settings))

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


async def test_push_file_with_spaces_in_name_to_remote(
    remote_parameters: StorageParameters,
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    # let's create some file with spaces/parentheses in its local name
    src_path = tmp_path / "some file with spaces (1) (2).txt"
    TEXT_IN_FILE = faker.text()
    src_path.write_text(TEXT_IN_FILE)
    assert src_path.exists()
    # push it to the remote
    await push_file_to_remote(
        src_path,
        remote_parameters.remote_file_url,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
        encryption=None,
    )

    # check the remote is actually having the file in
    storage_kwargs = {}
    if remote_parameters.s3_settings:
        storage_kwargs = cast(dict, _s3fs_settings_from_s3_settings(remote_parameters.s3_settings))

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
    tmp_path: Path,
    s3_bucket: str,
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
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=None,
        encryption=None,
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
    destination_url = TypeAdapter(AnyUrl).validate_python(f"{remote_parameters.remote_file_url}.zip")
    src_path = tmp_path / faker.file_name()
    TEXT_IN_FILE = faker.text()
    src_path.write_text(TEXT_IN_FILE)
    assert src_path.exists()

    await push_file_to_remote(
        src_path,
        destination_url,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
        encryption=None,
    )

    storage_kwargs = {}
    if remote_parameters.s3_settings:
        storage_kwargs = cast(dict, _s3fs_settings_from_s3_settings(remote_parameters.s3_settings))
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
        storage_kwargs = cast(dict, _s3fs_settings_from_s3_settings(remote_parameters.s3_settings))
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
        encryption=None,
    )
    assert dst_path.exists()
    assert dst_path.read_text() == TEXT_IN_FILE
    mocked_log_publishing_cb.assert_called()


async def test_push_file_to_remote_logs_progress_when_elapsed_time_is_zero(
    mocker: MockerFixture,
    tmp_path: Path,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    src_path = tmp_path / "payload.txt"
    src_path.write_bytes(b"payload")
    dst_path = tmp_path / "uploaded.txt"
    mocker.patch(
        "simcore_service_dask_sidecar.utils.files.time.perf_counter",
        return_value=10.0,
    )

    await push_file_to_remote(
        src_path,
        TypeAdapter(AnyUrl).validate_python(dst_path.as_uri()),
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=None,
        encryption=None,
    )

    assert dst_path.read_bytes() == b"payload"
    progress_messages = [
        call.args[0] for call in mocked_log_publishing_cb.await_args_list if "MBytes/s (avg)" in call.args[0]
    ]
    assert progress_messages
    assert any("100.0%" in message for message in progress_messages)
    assert all("[0.00 MBytes/s (avg)]" in message for message in progress_messages)


async def test_push_file_to_remote_encrypts_with_crypto_context(
    tmp_path: Path,
    mocked_log_publishing_cb: mock.AsyncMock,
    encryption_settings: TransferEncryptionSettings,
):
    src_path = tmp_path / "plain.txt"
    src_bytes = b"top-secret payload"
    src_path.write_bytes(src_bytes)
    encrypted_path = tmp_path / "encrypted.bin"

    await push_file_to_remote(
        src_path,
        TypeAdapter(AnyUrl).validate_python(encrypted_path.as_uri()),
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=None,
        encryption=encryption_settings,
    )

    assert encrypted_path.exists()
    encrypted_bytes = encrypted_path.read_bytes()
    assert encrypted_bytes != src_bytes
    assert encrypted_bytes.startswith(FORMAT_MAGIC)
    mocked_log_publishing_cb.assert_called()


async def test_push_then_pull_file_decrypts_with_crypto_context(
    tmp_path: Path,
    mocked_log_publishing_cb: mock.AsyncMock,
    encryption_settings: TransferEncryptionSettings,
):
    src_path = tmp_path / "plain.txt"
    src_bytes = b"top-secret payload"
    src_path.write_bytes(src_bytes)
    encrypted_path = tmp_path / "encrypted.bin"
    decrypted_path = tmp_path / "decrypted.txt"

    await push_file_to_remote(
        src_path,
        TypeAdapter(AnyUrl).validate_python(encrypted_path.as_uri()),
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=None,
        encryption=encryption_settings,
    )
    await pull_file_from_remote(
        src_url=TypeAdapter(AnyUrl).validate_python(encrypted_path.as_uri()),
        target_mime_type=None,
        dst_path=decrypted_path,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=None,
        encryption=encryption_settings,
    )

    assert decrypted_path.exists()
    assert decrypted_path.read_bytes() == src_bytes
    mocked_log_publishing_cb.assert_called()


async def test_pull_file_from_remote_decrypt_with_wrong_key_raises_auth_error(
    tmp_path: Path,
    mocked_log_publishing_cb: mock.AsyncMock,
    encryption_settings: TransferEncryptionSettings,
):
    src_path = tmp_path / "plain.txt"
    src_bytes = b"top-secret payload"
    src_path.write_bytes(src_bytes)
    encrypted_path = tmp_path / "encrypted.bin"
    decrypted_path = tmp_path / "decrypted.txt"

    await push_file_to_remote(
        src_path,
        TypeAdapter(AnyUrl).validate_python(encrypted_path.as_uri()),
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=None,
        encryption=encryption_settings,
    )

    wrong_key_settings = TransferEncryptionSettings(
        job_key=TypeAdapter(SecretBytes).validate_python(generate_key()),
        job_id=encryption_settings.job_id,
        file_id=encryption_settings.file_id,
        file_role=encryption_settings.file_role,
    )
    with pytest.raises(AesGcmStreamAuthError, match="authentication failed"):
        await pull_file_from_remote(
            src_url=TypeAdapter(AnyUrl).validate_python(encrypted_path.as_uri()),
            target_mime_type=None,
            dst_path=decrypted_path,
            log_publishing_cb=mocked_log_publishing_cb,
            s3_settings=None,
            encryption=wrong_key_settings,
        )


@pytest.mark.parametrize("scheme", ["http", "https"])
async def test_push_file_to_remote_with_encryption_to_http_raises(
    scheme: str,
    tmp_path: Path,
    mocked_log_publishing_cb: mock.AsyncMock,
    encryption_settings: TransferEncryptionSettings,
):
    src_path = tmp_path / "plain.txt"
    src_path.write_bytes(b"top-secret payload")

    with pytest.raises(
        HTTPDestinationEncryptionNotSupportedError,
        match=f"Encryption is not supported for {scheme} upload destinations",
    ):
        await push_file_to_remote(
            src_path,
            TypeAdapter(AnyUrl).validate_python(f"{scheme}://example.com/upload"),
            log_publishing_cb=mocked_log_publishing_cb,
            s3_settings=None,
            encryption=encryption_settings,
        )


async def test_push_then_pull_file_with_encryption_roundtrip(
    remote_parameters: StorageParameters,
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
    encryption_settings: TransferEncryptionSettings,
):
    src_path = tmp_path / faker.file_name()
    plain_text = faker.text()
    src_path.write_text(plain_text)

    await push_file_to_remote(
        src_path,
        remote_parameters.remote_file_url,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
        encryption=encryption_settings,
    )

    storage_kwargs = {}
    if remote_parameters.s3_settings:
        storage_kwargs = cast(dict, _s3fs_settings_from_s3_settings(remote_parameters.s3_settings))
    with cast(
        fsspec.core.OpenFile,
        fsspec.open(
            f"{remote_parameters.remote_file_url}",
            mode="rb",
            **storage_kwargs,
        ),
    ) as fp:
        remote_data = fp.read()
    assert remote_data != plain_text.encode()
    assert remote_data.startswith(FORMAT_MAGIC)

    dst_path = tmp_path / faker.file_name()
    await pull_file_from_remote(
        src_url=remote_parameters.remote_file_url,
        target_mime_type=None,
        dst_path=dst_path,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
        encryption=encryption_settings,
    )

    assert dst_path.exists()
    assert dst_path.read_text() == plain_text
    mocked_log_publishing_cb.assert_called()


async def test_pull_file_from_remote_s3_presigned_link(
    s3_settings: S3Settings,
    s3_remote_file_url: AnyUrl,
    s3_client: S3Client,
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
        await s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": s3_settings.S3_BUCKET_NAME,
                "Key": f"{s3_remote_file_url.path.removeprefix('/')}",
            },
            ExpiresIn=30,
        )
    )
    assert remote_file_url.scheme.startswith("http")
    print(f"remote_file_url: {remote_file_url}")
    # now let's get the file through the util
    dst_path = tmp_path / faker.file_name()
    await pull_file_from_remote(
        src_url=remote_file_url,
        target_mime_type=None,
        dst_path=dst_path,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=None,
        encryption=None,
    )
    assert dst_path.exists()
    assert dst_path.read_text() == TEXT_IN_FILE
    mocked_log_publishing_cb.assert_called()


async def test_pull_file_from_remote_s3_presigned_link_invalid_file(
    s3_settings: S3Settings,
    s3_remote_file_url: AnyUrl,
    s3_client: S3Client,
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
    invalid_remote_file_url = TypeAdapter(AnyUrl).validate_python(
        await s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": s3_settings.S3_BUCKET_NAME,
                "Key": f"{s3_remote_file_url.path.removeprefix('/')}_invalid",
            },
            ExpiresIn=30,
        )
    )
    assert invalid_remote_file_url.scheme.startswith("http")
    print(f"remote_file_url: {invalid_remote_file_url}")
    # now let's get the file through the util
    dst_path = tmp_path / faker.file_name()
    with pytest.raises(
        FileNotFoundError,
        match=rf"{s3_remote_file_url.path.removeprefix('/')}_invalid",
    ):
        await pull_file_from_remote(
            src_url=invalid_remote_file_url,
            target_mime_type=None,
            dst_path=dst_path,
            log_publishing_cb=mocked_log_publishing_cb,
            s3_settings=None,
            encryption=None,
        )

    assert not dst_path.exists()
    mocked_log_publishing_cb.assert_called()


async def test_pull_compressed_zip_file_from_remote(
    remote_parameters: StorageParameters,
    upload_file_to_remote: Callable[[Path, AnyUrl], None],
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    # put some zip file on the remote
    local_zip_file_path = tmp_path / f"{faker.file_name()}.zip"
    file_names_within_zip_file = set()
    with zipfile.ZipFile(local_zip_file_path, compression=zipfile.ZIP_DEFLATED, mode="w") as zfp:
        for file_number in range(5):
            local_test_file = tmp_path / f"{file_number}_{faker.file_name()}"
            local_test_file.write_text(faker.text())
            assert local_test_file.exists()
            zfp.write(local_test_file, local_test_file.name)
            file_names_within_zip_file.add(local_test_file.name)

    destination_url = TypeAdapter(AnyUrl).validate_python(f"{remote_parameters.remote_file_url}.zip")
    upload_file_to_remote(local_zip_file_path, destination_url)

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
        encryption=None,
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
        encryption=None,
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
    mime_type, _ = mimetypes.guess_type(faker.file_name())  # let's have a standard mime type
    await pull_file_from_remote(
        src_url=src_url,
        target_mime_type=mime_type,
        dst_path=dst_path,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
        encryption=None,
    )
    assert not dst_path.exists()
    for file in download_folder.glob("*"):
        assert file.exists()
        assert file.name in file_names_within_zip_file
    mocked_log_publishing_cb.assert_called()


async def test_pull_compressed_zip_file_with_spaces_in_name_from_remote(
    remote_parameters: StorageParameters,
    upload_file_to_remote: Callable[[Path, AnyUrl], None],
    tmp_path: Path,
    faker: Faker,
    mocked_log_publishing_cb: mock.AsyncMock,
):
    local_zip_file_path = tmp_path / "archive with spaces (1) (2).zip"
    file_names_within_zip_file = set()
    with zipfile.ZipFile(local_zip_file_path, compression=zipfile.ZIP_DEFLATED, mode="w") as zfp:
        for file_number in range(5):
            local_test_file = tmp_path / f"{file_number}_{faker.file_name()}"
            local_test_file.write_text(faker.text())
            assert local_test_file.exists()
            zfp.write(local_test_file, local_test_file.name)
            file_names_within_zip_file.add(local_test_file.name)

    # NOTE: the remote file name contains spaces, which get percent-encoded in the URL
    destination_url = TypeAdapter(AnyUrl).validate_python(
        f"{remote_parameters.remote_file_url} with spaces (1) (2).zip"
    )

    assert "%20" in f"{destination_url}"
    assert " " not in f"{destination_url}"

    upload_file_to_remote(local_zip_file_path, destination_url)

    # now we want to download that file so it becomes the source
    src_url = destination_url

    # if destination is not a zip, then we decompress
    download_folder = tmp_path / "download"
    download_folder.mkdir(parents=True, exist_ok=True)
    assert download_folder.exists()
    dst_path = download_folder / faker.file_name()
    await pull_file_from_remote(
        src_url=src_url,
        target_mime_type=None,
        dst_path=dst_path,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
        encryption=None,
    )
    assert not dst_path.exists()
    extracted_file_names = {file.name for file in download_folder.glob("*")}
    assert extracted_file_names == file_names_within_zip_file
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
    destination_url1 = TypeAdapter(AnyUrl).validate_python(f"{remote_parameters.remote_file_url}1.zip")
    destination_url2 = TypeAdapter(AnyUrl).validate_python(f"{remote_parameters.remote_file_url}2.zip")
    src_path = tmp_path / faker.file_name()
    TEXT_IN_FILE = faker.text()
    src_path.write_text(TEXT_IN_FILE)
    assert src_path.exists()

    # pushing 2 times should produce the same archive with the same hash
    await push_file_to_remote(
        src_path,
        destination_url1,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
        encryption=None,
    )
    await asyncio.sleep(
        5
    )  # NOTE: we wait a bit to ensure the created zipfile has a different creation time (that is normally used for computing the hash)
    await push_file_to_remote(
        src_path,
        destination_url2,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
        encryption=None,
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
        encryption=None,
    )
    assert dst_path1.exists()

    await pull_file_from_remote(
        src_url=destination_url2,
        target_mime_type=None,
        dst_path=dst_path2,
        log_publishing_cb=mocked_log_publishing_cb,
        s3_settings=remote_parameters.s3_settings,
        encryption=None,
    )
    assert dst_path2.exists()

    assert _compute_hash(dst_path1) == _compute_hash(dst_path2)
