import asyncio
import functools
import logging
import mimetypes
import time
import zipfile
from collections.abc import Awaitable, Callable
from io import IOBase
from pathlib import Path
from typing import Any, Final, TypedDict, cast

import aiofiles
import aiofiles.tempfile
import fsspec  # type: ignore[import-untyped]
import repro_zipfile  # type: ignore[import-untyped]
from pydantic import ByteSize, FileUrl, TypeAdapter
from pydantic.networks import AnyUrl
from servicelib.logging_utils import LogLevelInt, LogMessageStr
from settings_library.s3 import S3Settings
from yarl import URL

logger = logging.getLogger(__name__)

HTTP_FILE_SYSTEM_SCHEMES: Final = ["http", "https"]
S3_FILE_SYSTEM_SCHEMES: Final = ["s3", "s3a"]


LogPublishingCB = Callable[[LogMessageStr, LogLevelInt], Awaitable[None]]


def _file_progress_cb(
    size,
    value,
    log_publishing_cb: LogPublishingCB,
    text_prefix: str,
    main_loop: asyncio.AbstractEventLoop,
    **kwargs,  # noqa: ARG001
):
    asyncio.run_coroutine_threadsafe(
        log_publishing_cb(
            f"{text_prefix}"
            f" {100.0 * float(value or 0)/float(size or 1):.1f}%"
            f" ({ByteSize(value).human_readable() if value else 0} / {ByteSize(size).human_readable() if size else 'NaN'})",
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


_DEFAULT_AWS_REGION: Final[str] = "us-east-1"


def _s3fs_settings_from_s3_settings(s3_settings: S3Settings) -> S3FsSettingsDict:
    s3fs_settings: S3FsSettingsDict = {
        "key": s3_settings.S3_ACCESS_KEY,
        "secret": s3_settings.S3_SECRET_KEY,
        "client_kwargs": {},
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


async def _copy_file(
    src_url: AnyUrl,
    dst_url: AnyUrl,
    *,
    log_publishing_cb: LogPublishingCB,
    text_prefix: str,
    src_storage_cfg: dict[str, Any] | None = None,
    dst_storage_cfg: dict[str, Any] | None = None,
):
    src_storage_kwargs = src_storage_cfg or {}
    dst_storage_kwargs = dst_storage_cfg or {}
    with fsspec.open(
        f"{src_url}", mode="rb", **src_storage_kwargs
    ) as src_fp, fsspec.open(f"{dst_url}", "wb", **dst_storage_kwargs) as dst_fp:
        assert isinstance(src_fp, IOBase)  # nosec
        assert isinstance(dst_fp, IOBase)  # nosec
        file_size = getattr(src_fp, "size", None)
        data_read = True
        total_data_written = 0
        t = time.process_time()
        while data_read:
            (data_read, data_written,) = await asyncio.get_event_loop().run_in_executor(
                None, _file_chunk_streamer, src_fp, dst_fp
            )
            elapsed_time = time.process_time() - t
            total_data_written += data_written or 0
            await log_publishing_cb(
                f"{text_prefix}"
                f" {100.0 * float(total_data_written or 0)/float(file_size or 1):.1f}%"
                f" ({ByteSize(total_data_written).human_readable() if total_data_written else 0} / {ByteSize(file_size).human_readable() if file_size else 'NaN'})"
                f" [{ByteSize(total_data_written).to('MB')/elapsed_time:.2f} MBytes/s (avg)]",
                logging.DEBUG,
            )


_ZIP_MIME_TYPE: Final[str] = "application/zip"


async def pull_file_from_remote(
    src_url: AnyUrl,
    target_mime_type: str | None,
    dst_path: Path,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
) -> None:
    assert src_url.path  # nosec
    await log_publishing_cb(
        f"Downloading '{src_url}' into local file '{dst_path}'...",
        logging.INFO,
    )
    if not dst_path.parent.exists():
        msg = f"{dst_path.parent=} does not exist. It must be created by the caller"
        raise ValueError(msg)

    src_mime_type, _ = mimetypes.guess_type(f"{src_url.path}")
    if not target_mime_type:
        target_mime_type, _ = mimetypes.guess_type(dst_path)

    storage_kwargs: S3FsSettingsDict | dict[str, Any] = {}
    if s3_settings and src_url.scheme in S3_FILE_SYSTEM_SCHEMES:
        storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)
    await _copy_file(
        src_url,
        TypeAdapter(FileUrl).validate_python(dst_path.as_uri()),
        src_storage_cfg=cast(dict[str, Any], storage_kwargs),
        log_publishing_cb=log_publishing_cb,
        text_prefix=f"Downloading '{src_url.path.strip('/')}':",
    )

    await log_publishing_cb(
        f"Download of '{src_url}' into local file '{dst_path}' complete.",
        logging.INFO,
    )

    if src_mime_type == _ZIP_MIME_TYPE and target_mime_type != _ZIP_MIME_TYPE:
        await log_publishing_cb(f"Uncompressing '{dst_path.name}'...", logging.INFO)
        logger.debug("%s is a zip file and will be now uncompressed", dst_path)
        with repro_zipfile.ReproducibleZipFile(dst_path, "r") as zip_obj:
            await asyncio.get_event_loop().run_in_executor(
                None, zip_obj.extractall, dst_path.parents[0]
            )
        # finally remove the zip archive
        await log_publishing_cb(
            f"Uncompressing '{dst_path.name}' complete.", logging.INFO
        )
        dst_path.unlink()


async def _push_file_to_http_link(
    file_to_upload: Path, dst_url: AnyUrl, log_publishing_cb: LogPublishingCB
) -> None:
    # NOTE: special case for http scheme when uploading. this is typically a S3 put presigned link.
    # Therefore, we need to use the http filesystem directly in order to call the put_file function.
    # writing on httpfilesystem is disabled by default.
    fs = fsspec.filesystem(
        "http",
        headers={
            "Content-Length": f"{file_to_upload.stat().st_size}",
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
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
) -> None:
    logger.debug("Uploading %s to %s...", file_to_upload, dst_url)
    assert dst_url.path  # nosec

    storage_kwargs: S3FsSettingsDict | dict[str, Any] = {}
    if s3_settings:
        storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)

    await _copy_file(
        TypeAdapter(FileUrl).validate_python(file_to_upload.as_uri()),
        dst_url,
        dst_storage_cfg=cast(dict[str, Any], storage_kwargs),
        log_publishing_cb=log_publishing_cb,
        text_prefix=f"Uploading '{dst_url.path.strip('/')}':",
    )


MIMETYPE_APPLICATION_ZIP = "application/zip"


async def push_file_to_remote(
    src_path: Path,
    dst_url: AnyUrl,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
) -> None:
    if not src_path.exists():
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

            with repro_zipfile.ReproducibleZipFile(
                archive_file_path, mode="w", compression=zipfile.ZIP_STORED
            ) as zfp:
                await asyncio.get_event_loop().run_in_executor(
                    None, zfp.write, src_path, src_path.name
                )
            logger.debug("%s created.", archive_file_path)
            assert archive_file_path.exists()  # nosec
            file_to_upload = archive_file_path
            await log_publishing_cb(
                f"Compression of '{src_path.name}' to '{archive_file_path.name}' complete.",
                logging.INFO,
            )

        await log_publishing_cb(
            f"Uploading '{file_to_upload.name}' to '{dst_url}'...", logging.INFO
        )

        if dst_url.scheme in HTTP_FILE_SYSTEM_SCHEMES:
            logger.debug("destination is a http presigned link")
            await _push_file_to_http_link(file_to_upload, dst_url, log_publishing_cb)
        else:
            await _push_file_to_remote(
                file_to_upload, dst_url, log_publishing_cb, s3_settings
            )

    await log_publishing_cb(
        f"Upload of '{src_path.name}' to '{dst_url.path.strip('/')}' complete",
        logging.INFO,
    )
