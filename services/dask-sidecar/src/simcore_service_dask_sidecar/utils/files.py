import asyncio
import functools
import logging
import mimetypes
import time
import zipfile
from collections.abc import Callable, Coroutine
from contextlib import AsyncExitStack
from io import IOBase
from pathlib import Path
from typing import Any, BinaryIO, Final, Literal, TypedDict, cast

import aiofiles
import aiofiles.os
import aiofiles.tempfile
import fsspec  # type: ignore[import-untyped]
import repro_zipfile
from dask_task_models_library.container_tasks.encryption import (
    TransferEncryptionSettings,
)
from pydantic import ByteSize
from pydantic.networks import AnyUrl
from servicelib.logging_utils import LogLevelInt, LogMessageStr
from settings_library.s3 import S3Settings
from yarl import URL

from ..aes_gcm import decrypt_stream, encrypt_stream
from ..errors import HTTPDestinationEncryptionNotSupportedError

logger = logging.getLogger(__name__)

HTTP_FILE_SYSTEM_SCHEMES: Final = ["http", "https"]
S3_FILE_SYSTEM_SCHEMES: Final = ["s3", "s3a"]


LogPublishingCB = Callable[[LogMessageStr, LogLevelInt], Coroutine[Any, Any, None]]


def _file_progress_cb(
    size,
    value,
    log_publishing_cb: LogPublishingCB,
    text_prefix: str,
    main_loop: asyncio.AbstractEventLoop,
    **kwargs,  # noqa: ARG001
):
    value_readable = ByteSize(value).human_readable() if value else 0
    size_readable = ByteSize(size).human_readable() if size else "NaN"
    asyncio.run_coroutine_threadsafe(
        log_publishing_cb(
            f"{text_prefix} {100.0 * float(value or 0) / float(size or 1):.1f}% ({value_readable} / {size_readable})",
            logging.DEBUG,
        ),
        main_loop,
    )


CHUNK_SIZE = 4 * 1024 * 1024


class ClientKWArgsDict(TypedDict, total=False):
    endpoint_url: str
    region_name: str


class S3FsSettingsDict(TypedDict):
    key: str
    secret: str
    client_kwargs: ClientKWArgsDict
    config_kwargs: dict[str, str]  # For botocore config options


_DEFAULT_AWS_REGION: Final[str] = "us-east-1"
_TransferMode = Literal["encrypt", "decrypt"]


def _s3fs_settings_from_s3_settings(s3_settings: S3Settings) -> S3FsSettingsDict:
    s3fs_settings: S3FsSettingsDict = {
        "key": s3_settings.S3_ACCESS_KEY.get_secret_value(),
        "secret": s3_settings.S3_SECRET_KEY.get_secret_value(),
        "client_kwargs": {},
        "config_kwargs": {
            # This setting tells the S3 client to only calculate checksums when explicitly required
            # by the operation. This avoids unnecessary checksum calculations for operations that
            # don't need them, improving performance.
            # See: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3.html#calculating-checksums
            "request_checksum_calculation": "when_required",
            "signature_version": "s3v4",
        },
    }
    if s3_settings.S3_REGION != _DEFAULT_AWS_REGION:
        # NOTE: see https://github.com/boto/boto3/issues/125 why this is so... (sic)
        # setting it for the us-east-1 creates issue when creating buckets (which we do in tests)
        s3fs_settings["client_kwargs"]["region_name"] = s3_settings.S3_REGION
    if s3_settings.S3_ENDPOINT is not None:
        s3fs_settings["client_kwargs"]["endpoint_url"] = f"{s3_settings.S3_ENDPOINT}"
    return s3fs_settings


def _file_chunk_streamer(src: IOBase, dst: IOBase):
    data = src.read(CHUNK_SIZE)
    segment_len = dst.write(data)
    return (data, segment_len)


def _format_progress_message(
    *,
    text_prefix: str,
    bytes_transferred: int,
    file_size: int | None,
    elapsed_time: float,
) -> str:
    speed_mbps = ByteSize(bytes_transferred).to("MB") / elapsed_time if elapsed_time > 0 else 0.0
    return (
        f"{text_prefix}"
        f" {100.0 * float(bytes_transferred or 0) / float(file_size or 1):.1f}%"
        f" ({ByteSize(bytes_transferred).human_readable() if bytes_transferred else 0} / "
        f"{ByteSize(file_size).human_readable() if file_size else 'NaN'})"
        f" [{speed_mbps:.2f} MBytes/s (avg)]"
    )


class _ThreadSafeProgressLogger:
    """Thread-safe progress callback for blocking transfers run in an executor.

    The callback is invoked from a worker thread with the cumulative number of
    plaintext bytes processed so far, and schedules throttled progress logs back onto
    the main event loop via ``asyncio.run_coroutine_threadsafe``.
    """

    _MIN_PERCENT_DELTA: Final[float] = 1.0
    _MIN_INTERVAL_SECONDS: Final[float] = 1.0

    def __init__(
        self,
        *,
        file_size: int | None,
        log_publishing_cb: LogPublishingCB,
        text_prefix: str,
        main_loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._file_size = file_size
        self._log_publishing_cb = log_publishing_cb
        self._text_prefix = text_prefix
        self._main_loop = main_loop
        self._start_time = time.monotonic()
        self._last_emit_time = self._start_time
        self._last_logged_percent = -1.0
        self._bytes_processed = 0

    def __call__(self, bytes_processed: int) -> None:
        # NOTE: invoked from the executor worker thread
        self._bytes_processed = bytes_processed
        now = time.monotonic()
        percent = 100.0 * float(bytes_processed) / float(self._file_size) if self._file_size else 0.0
        enough_progress = percent - self._last_logged_percent >= self._MIN_PERCENT_DELTA
        enough_time = now - self._last_emit_time >= self._MIN_INTERVAL_SECONDS
        if not (enough_progress or enough_time):
            return
        self._last_logged_percent = percent
        self._last_emit_time = now
        asyncio.run_coroutine_threadsafe(
            self._log_publishing_cb(self._build_message(now), logging.DEBUG),
            self._main_loop,
        )

    async def emit_final(self) -> None:
        # NOTE: called on completion from the main event loop
        await self._log_publishing_cb(self._build_message(time.monotonic()), logging.DEBUG)

    def _build_message(self, now: float) -> str:
        return _format_progress_message(
            text_prefix=self._text_prefix,
            bytes_transferred=self._bytes_processed,
            file_size=self._file_size,
            elapsed_time=now - self._start_time,
        )


async def _run_plain_copy(
    src_fp: IOBase,
    dst_fp: IOBase,
    *,
    file_size: int | None,
    log_publishing_cb: LogPublishingCB,
    text_prefix: str,
) -> None:
    data_read = True
    total_data_written = 0
    t = time.perf_counter()
    while data_read:
        (
            data_read,
            data_written,
        ) = await asyncio.get_event_loop().run_in_executor(None, _file_chunk_streamer, src_fp, dst_fp)
        elapsed_time = time.perf_counter() - t
        total_data_written += data_written or 0
        await log_publishing_cb(
            _format_progress_message(
                text_prefix=text_prefix,
                bytes_transferred=total_data_written,
                file_size=file_size,
                elapsed_time=elapsed_time,
            ),
            logging.DEBUG,
        )


async def _run_crypto_copy(
    src_fp: IOBase,
    dst_fp: IOBase,
    *,
    file_size: int | None,
    encryption: TransferEncryptionSettings,
    encryption_mode: _TransferMode,
    log_publishing_cb: LogPublishingCB,
    text_prefix: str,
) -> None:
    main_loop = asyncio.get_running_loop()
    progress_logger = _ThreadSafeProgressLogger(
        file_size=file_size,
        log_publishing_cb=log_publishing_cb,
        text_prefix=text_prefix,
        main_loop=main_loop,
    )
    transfer = encrypt_stream if encryption_mode == "encrypt" else decrypt_stream
    blocking_transfer = functools.partial(
        transfer,
        cast(BinaryIO, src_fp),
        cast(BinaryIO, dst_fp),
        job_key=encryption.job_key.get_secret_value(),
        job_id=encryption.job_id,
        file_id=encryption.file_id,
        file_role=encryption.file_role,
        progress_cb=progress_logger,
    )
    await main_loop.run_in_executor(None, blocking_transfer)
    # force a final progress log on completion
    await progress_logger.emit_final()


async def _copy_file(
    src_url: AnyUrl | Path,
    dst_url: AnyUrl | Path,
    *,
    log_publishing_cb: LogPublishingCB,
    text_prefix: str,
    src_storage_cfg: dict[str, Any] | None,
    dst_storage_cfg: dict[str, Any] | None,
    encryption: TransferEncryptionSettings | None,
    encryption_mode: _TransferMode | None,
):
    src_storage_kwargs = src_storage_cfg or {}
    dst_storage_kwargs = dst_storage_cfg or {}
    with (
        fsspec.open(f"{src_url}", mode="rb", expand=False, **src_storage_kwargs) as src_fp,
        fsspec.open(f"{dst_url}", mode="wb", expand=False, **dst_storage_kwargs) as dst_fp,
    ):
        assert isinstance(src_fp, IOBase)  # nosec
        assert isinstance(dst_fp, IOBase)  # nosec
        file_size = getattr(src_fp, "size", None)
        if encryption is None:
            await _run_plain_copy(
                src_fp,
                dst_fp,
                file_size=file_size,
                log_publishing_cb=log_publishing_cb,
                text_prefix=text_prefix,
            )
        else:
            if encryption_mode is None:
                msg = "encryption_mode must be provided when encryption settings are configured"
                raise ValueError(msg)
            await _run_crypto_copy(
                src_fp,
                dst_fp,
                file_size=file_size,
                encryption=encryption,
                encryption_mode=encryption_mode,
                log_publishing_cb=log_publishing_cb,
                text_prefix=text_prefix,
            )


_ZIP_MIME_TYPE: Final[str] = "application/zip"


def check_need_unzipping(
    src_url: AnyUrl,
    target_mime_type: str | None,
    dst_path: Path,
) -> bool:
    """
    Checks if the source URL points to a zip file and if the target mime type is not zip.
    If so, extraction is needed.
    """
    assert src_url.path  # nosec
    src_mime_type, _ = mimetypes.guess_type(src_url.path)
    dst_mime_type = target_mime_type
    if not dst_mime_type:
        dst_mime_type, _ = mimetypes.guess_type(dst_path)
    return (src_mime_type == _ZIP_MIME_TYPE) and (dst_mime_type != _ZIP_MIME_TYPE)


async def pull_file_from_remote(
    src_url: AnyUrl,
    target_mime_type: str | None,
    dst_path: Path,
    *,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
    encryption: TransferEncryptionSettings | None,
) -> None:
    assert src_url.path  # nosec
    src_location_str = f"{src_url.path.strip('/')} on {src_url.host}:{src_url.port}"
    await log_publishing_cb(
        f"Downloading '{src_location_str}' into local file '{dst_path}'...",
        logging.INFO,
    )
    if not dst_path.parent.exists():
        msg = f"{dst_path.parent=} does not exist. It must be created by the caller"
        raise ValueError(msg)

    storage_kwargs: S3FsSettingsDict | dict[str, Any] = {}
    if s3_settings and src_url.scheme in S3_FILE_SYSTEM_SCHEMES:
        storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)

    need_unzipping = check_need_unzipping(src_url, target_mime_type, dst_path)
    async with AsyncExitStack() as exit_stack:
        if need_unzipping:
            # we need to extract the file, so we create a temporary directory
            # where the file will be downloaded and extracted
            tmp_dir = await exit_stack.enter_async_context(aiofiles.tempfile.TemporaryDirectory())
            # NOTE: the URL path is percent-encoded
            download_dst_path = Path(tmp_dir) / Path(URL(f"{src_url}").path).name
        else:
            # no extraction needed, so we can use the provided dst_path directly
            download_dst_path = dst_path

        await _copy_file(
            src_url,
            download_dst_path,
            src_storage_cfg=cast(dict[str, Any], storage_kwargs),
            dst_storage_cfg=None,
            log_publishing_cb=log_publishing_cb,
            text_prefix=f"Downloading '{src_location_str}':",
            encryption=encryption,
            encryption_mode="decrypt" if encryption else None,
        )

        await log_publishing_cb(
            f"Download of '{src_location_str}' into local file '{download_dst_path}' complete.",
            logging.INFO,
        )

        if need_unzipping:
            await log_publishing_cb(f"Uncompressing '{download_dst_path.name}'...", logging.INFO)
            logger.debug("%s is a zip file and will be now uncompressed", download_dst_path)
            with repro_zipfile.ReproducibleZipFile(download_dst_path, "r") as zip_obj:
                await asyncio.get_event_loop().run_in_executor(None, zip_obj.extractall, dst_path.parents[0])
            # finally remove the zip archive
            await log_publishing_cb(f"Uncompressing '{download_dst_path.name}' complete.", logging.INFO)


async def _push_file_to_http_link(file_to_upload: Path, dst_url: AnyUrl, log_publishing_cb: LogPublishingCB) -> None:
    # NOTE: special case for http scheme when uploading. this is typically a S3 put presigned link.
    # Therefore, we need to use the http filesystem directly in order to call the put_file function.
    # writing on httpfilesystem is disabled by default.
    fs = fsspec.filesystem(
        "http",
        headers={
            "Content-Length": f"{(await aiofiles.os.stat(file_to_upload)).st_size}",
        },
        asynchronous=True,
    )
    assert dst_url.path  # nosec
    await fs._put_file(  # pylint: disable=protected-access  # noqa: SLF001
        file_to_upload,
        f"{dst_url}",
        method="PUT",
        callback=fsspec.Callback(
            hooks={
                "progress": functools.partial(
                    _file_progress_cb,
                    log_publishing_cb=log_publishing_cb,
                    text_prefix=f"Uploading '{dst_url.path.strip('/')}':",
                    main_loop=asyncio.get_event_loop(),
                )
            }
        ),
    )


async def _push_file_to_remote(
    file_to_upload: Path,
    dst_url: AnyUrl,
    *,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
    encryption: TransferEncryptionSettings | None,
) -> None:
    logger.debug("Uploading %s to %s...", file_to_upload, dst_url)
    assert dst_url.path  # nosec

    storage_kwargs: S3FsSettingsDict | dict[str, Any] = {}
    if s3_settings:
        storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)

    await _copy_file(
        file_to_upload,
        dst_url,
        src_storage_cfg=None,
        dst_storage_cfg=cast(dict[str, Any], storage_kwargs),
        log_publishing_cb=log_publishing_cb,
        text_prefix=f"Uploading '{dst_url.path.strip('/')}':",
        encryption=encryption,
        encryption_mode="encrypt" if encryption else None,
    )


MIMETYPE_APPLICATION_ZIP = "application/zip"


async def push_file_to_remote(
    src_path: Path,
    dst_url: AnyUrl,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
    encryption: TransferEncryptionSettings | None,
) -> None:
    if not await aiofiles.os.path.exists(src_path):
        msg = f"{src_path=} does not exist"
        raise ValueError(msg)
    assert dst_url.path  # nosec
    async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
        file_to_upload = src_path

        dst_mime_type, _ = mimetypes.guess_type(f"{dst_url.path}")
        src_mime_type, _ = mimetypes.guess_type(src_path)

        if dst_mime_type == _ZIP_MIME_TYPE and src_mime_type != _ZIP_MIME_TYPE:
            archive_file_path = Path(tmp_dir) / Path(URL(f"{dst_url}").path).name
            await log_publishing_cb(
                f"Compressing '{src_path.name}' to '{archive_file_path.name}'...",
                logging.INFO,
            )

            with repro_zipfile.ReproducibleZipFile(archive_file_path, mode="w", compression=zipfile.ZIP_STORED) as zfp:
                await asyncio.get_event_loop().run_in_executor(None, zfp.write, src_path, src_path.name)
            logger.debug("%s created.", archive_file_path)
            assert archive_file_path.exists()  # nosec
            file_to_upload = archive_file_path
            await log_publishing_cb(
                f"Compression of '{src_path.name}' to '{archive_file_path.name}' complete.",
                logging.INFO,
            )

        await log_publishing_cb(f"Uploading '{file_to_upload.name}' to '{dst_url}'...", logging.INFO)

        if dst_url.scheme in HTTP_FILE_SYSTEM_SCHEMES:
            if encryption is not None:
                raise HTTPDestinationEncryptionNotSupportedError(scheme=dst_url.scheme)
            logger.debug("destination is a http presigned link")
            await _push_file_to_http_link(file_to_upload, dst_url, log_publishing_cb)
        else:
            await _push_file_to_remote(
                file_to_upload,
                dst_url,
                log_publishing_cb=log_publishing_cb,
                s3_settings=s3_settings,
                encryption=encryption,
            )

    await log_publishing_cb(
        f"Upload of '{src_path.name}' to '{dst_url.path.strip('/')}' complete",
        logging.INFO,
    )
