import asyncio
import functools
import logging
import mimetypes
import time
import zipfile
from io import BufferedReader, BytesIO
from pathlib import Path
from typing import Any, Awaitable, Callable, Final, Mapping, Optional, TypedDict, cast

import aiofiles
import aiofiles.tempfile
import aiohttp
import fsspec
from aiohttp import ClientSession
from dask_task_models_library.container_tasks.io import TaskOsparcAPISettings
from pydantic import ByteSize, FileUrl, parse_obj_as
from pydantic.networks import AnyUrl
from servicelib.logging_utils import log_catch, log_context
from settings_library.s3 import S3Settings
from yarl import URL

from .dask_utils import create_dask_worker_logger

logger = create_dask_worker_logger(__name__)

HTTP_FILE_SYSTEM_SCHEMES: Final = ["http", "https"]
S3_FILE_SYSTEM_SCHEMES: Final = ["s3", "s3a"]
CHUNK_SIZE = 4 * 1024 * 1024
MIMETYPE_APPLICATION_ZIP: Final[str] = "application/zip"

LogPublishingCB = Callable[[str], Awaitable[None]]


def _file_progress_cb(
    size,
    value,
    log_publishing_cb: LogPublishingCB,
    text_prefix: str,
    main_loop: asyncio.AbstractEventLoop,
    **kwargs,
):
    asyncio.run_coroutine_threadsafe(
        log_publishing_cb(
            f"{text_prefix}"
            f" {100.0 * float(value or 0)/float(size or 1):.1f}%"
            f" ({ByteSize(value).human_readable() if value else 0} / {ByteSize(size).human_readable() if size else 'NaN'})"
        ),
        main_loop,
    )


class ClientKWArgsDict(TypedDict):
    endpoint_url: str


class S3FsSettingsDict(TypedDict):
    key: str
    secret: str
    token: Optional[str]
    use_ssl: bool
    client_kwargs: ClientKWArgsDict


def _s3fs_settings_from_s3_settings(s3_settings: S3Settings) -> S3FsSettingsDict:
    return {
        "key": s3_settings.S3_ACCESS_KEY,
        "secret": s3_settings.S3_SECRET_KEY,
        "token": s3_settings.S3_ACCESS_TOKEN,
        "use_ssl": s3_settings.S3_SECURE,
        "client_kwargs": {"endpoint_url": s3_settings.S3_ENDPOINT},
    }


def _file_chunk_streamer(src: BytesIO, dst: BytesIO):
    data = src.read(CHUNK_SIZE)
    segment_len = dst.write(data)
    return (data, segment_len)


async def _copy_file(
    src_url: AnyUrl,
    dst_url: AnyUrl,
    *,
    log_publishing_cb: LogPublishingCB,
    text_prefix: str,
    src_storage_cfg: Optional[dict[str, Any]] = None,
    dst_storage_cfg: Optional[dict[str, Any]] = None,
):
    src_storage_kwargs = src_storage_cfg or {}
    dst_storage_kwargs = dst_storage_cfg or {}
    with fsspec.open(src_url, mode="rb", **src_storage_kwargs) as src_fp:
        with fsspec.open(dst_url, "wb", **dst_storage_kwargs) as dst_fp:
            file_size = getattr(src_fp, "size", None)
            data_read = True
            total_data_written = 0
            t = time.process_time()
            while data_read:
                (
                    data_read,
                    data_written,
                ) = await asyncio.get_event_loop().run_in_executor(
                    None, _file_chunk_streamer, src_fp, dst_fp
                )
                elapsed_time = time.process_time() - t
                total_data_written += data_written or 0
                await log_publishing_cb(
                    f"{text_prefix}"
                    f" {100.0 * float(total_data_written or 0)/float(file_size or 1):.1f}%"
                    f" ({ByteSize(total_data_written).human_readable() if total_data_written else 0} / {ByteSize(file_size).human_readable() if file_size else 'NaN'})"
                    f" [{ByteSize(total_data_written).to('MB')/elapsed_time:.2f} MBytes/s (avg)]"
                )


async def pull_file_from_remote(
    src_url: AnyUrl,
    target_mime_type: Optional[str],
    dst_path: Path,
    log_publishing_cb: LogPublishingCB,
    s3_settings: Optional[S3Settings],
) -> None:
    assert src_url.path  # nosec
    await log_publishing_cb(
        f"Downloading '{src_url.path.strip('/')}' into local file '{dst_path.name}'..."
    )
    if not dst_path.parent.exists():
        raise ValueError(
            f"{dst_path.parent=} does not exist. It must be created by the caller"
        )

    src_mime_type, _ = mimetypes.guess_type(f"{src_url.path}")
    if not target_mime_type:
        target_mime_type, _ = mimetypes.guess_type(dst_path)

    storage_kwargs: Mapping[str, Any] = {}
    if s3_settings and src_url.scheme in S3_FILE_SYSTEM_SCHEMES:
        storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)
    await _copy_file(
        src_url,
        parse_obj_as(FileUrl, dst_path.as_uri()),
        src_storage_cfg=cast(dict[str, Any], storage_kwargs),
        log_publishing_cb=log_publishing_cb,
        text_prefix=f"Downloading '{src_url.path.strip('/')}':",
    )

    await log_publishing_cb(
        f"Download of '{src_url.path.strip('/')}' into local file '{dst_path.name}' complete."
    )

    if (
        src_mime_type == MIMETYPE_APPLICATION_ZIP
        and target_mime_type != MIMETYPE_APPLICATION_ZIP
    ):
        await log_publishing_cb(f"Uncompressing '{dst_path.name}'...")
        logger.debug("%s is a zip file and will be now uncompressed", dst_path)
        with zipfile.ZipFile(dst_path, "r") as zip_obj:
            await asyncio.get_event_loop().run_in_executor(
                None, zip_obj.extractall, dst_path.parents[0]
            )
        # finally remove the zip archive
        await log_publishing_cb(f"Uncompressing '{dst_path.name}' complete.")
        dst_path.unlink()


async def _push_file_to_osparc_api(
    file_to_upload: Path,
    log_publishing_cb: LogPublishingCB,
    osparc_api_settings: TaskOsparcAPISettings,
) -> None:
    class ProgressFileReader(BufferedReader):
        """This is a trick to be able to update the reading file progress since it is not possible to use any kind of generator
        or at least I did not find how
        """

        def __init__(self, filename, read_callback, file_pointer):
            self.__read_callback = read_callback
            super().__init__(raw=file_pointer)
            self.length = Path(filename).stat().st_size

        def read(self, size=None):
            calc_sz = size
            if not calc_sz:
                calc_sz = self.length - self.tell()
            if self.__read_callback:
                self.__read_callback(self.length, self.tell())
            return super().read(size)

    osparc_files_api_url = URL(f"{osparc_api_settings.osparc_api_endpoint}").with_path(
        "/v0/files/content"
    )
    with log_context(logger, logging.DEBUG, msg="uploading to osparc API"), log_catch(
        logger
    ), file_to_upload.open("rb") as file:
        session = ClientSession()
        with ProgressFileReader(
            file_to_upload,
            functools.partial(
                _file_progress_cb,
                log_publishing_cb=log_publishing_cb,
                text_prefix=f"Uploading '{file_to_upload}':",
                main_loop=asyncio.get_event_loop(),
            ),
            file,
        ) as progress_file_reader:
            upload_payload = {"file": progress_file_reader}
            async with session.put(
                osparc_files_api_url,
                data=upload_payload,
                auth=aiohttp.BasicAuth(
                    osparc_api_settings.api_key, osparc_api_settings.api_secret
                ),
            ) as response:
                logger.debug("upload returned response: %s", await response.text())
                response.raise_for_status()


async def _push_file_to_http_link(
    file_to_upload: Path,
    dst_url: AnyUrl,
    log_publishing_cb: LogPublishingCB,
):
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
    await fs._put_file(  # pylint: disable=protected-access
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
    s3_settings: Optional[S3Settings],
):
    logger.debug("Uploading %s to %s...", file_to_upload, dst_url)
    assert dst_url.path  # nosec

    storage_kwargs: Mapping[str, Any] = {}
    if s3_settings:
        storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)

    await _copy_file(
        src_url=parse_obj_as(FileUrl, file_to_upload.as_uri()),
        dst_url=dst_url,
        dst_storage_cfg=cast(dict[str, Any], storage_kwargs),
        log_publishing_cb=log_publishing_cb,
        text_prefix=f"Uploading '{dst_url.path.strip('/')}':",
    )


async def push_file_to_remote(
    src_path: Path,
    dst_url: AnyUrl,
    log_publishing_cb: LogPublishingCB,
    s3_settings: Optional[S3Settings],
    osparc_api_settings: Optional[TaskOsparcAPISettings],
) -> None:
    if not src_path.exists():
        raise ValueError(f"{src_path=} does not exist")
    assert dst_url.path  # nosec
    async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
        file_to_upload = src_path

        dst_mime_type, _ = mimetypes.guess_type(f"{dst_url.path}")
        src_mime_type, _ = mimetypes.guess_type(src_path)

        if (
            dst_mime_type == MIMETYPE_APPLICATION_ZIP
            and src_mime_type != MIMETYPE_APPLICATION_ZIP
        ):
            archive_file_path = Path(tmp_dir) / Path(URL(dst_url).path).name
            await log_publishing_cb(
                f"Compressing '{src_path.name}' to '{archive_file_path.name}'..."
            )
            with zipfile.ZipFile(
                archive_file_path, mode="w", compression=zipfile.ZIP_DEFLATED
            ) as zfp:
                await asyncio.get_event_loop().run_in_executor(
                    None, zfp.write, src_path, src_path.name
                )
            logger.debug("%s created.", archive_file_path)
            assert archive_file_path.exists()  # nosec
            file_to_upload = archive_file_path
            await log_publishing_cb(
                f"Compression of '{src_path.name}' to '{archive_file_path.name}' complete."
            )

        await log_publishing_cb(f"Uploading '{file_to_upload.name}' to '{dst_url}'...")

        if osparc_api_settings:
            await _push_file_to_osparc_api(
                file_to_upload, log_publishing_cb, osparc_api_settings
            )
        elif dst_url.scheme in HTTP_FILE_SYSTEM_SCHEMES:
            await _push_file_to_http_link(file_to_upload, dst_url, log_publishing_cb)
        else:
            await _push_file_to_remote(
                file_to_upload, dst_url, log_publishing_cb, s3_settings
            )

    await log_publishing_cb(
        f"Upload of '{src_path.name}' to '{dst_url.path.strip('/')}' complete"
    )
