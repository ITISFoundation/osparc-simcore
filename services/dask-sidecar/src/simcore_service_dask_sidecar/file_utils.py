import asyncio
import functools
import mimetypes
import zipfile
from pathlib import Path
from typing import Awaitable, Callable, Final

import aiofiles
import aiofiles.tempfile
import fsspec
from pydantic import ByteSize
from pydantic.networks import AnyUrl
from yarl import URL

from .dask_utils import create_dask_worker_logger

logger = create_dask_worker_logger(__name__)

HTTP_FILE_SYSTEM_SCHEMES: Final = ["http", "https"]
S3_FILE_SYSTEM_SCHEMES: Final = ["s3", "s3a"]


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


CHUNK_SIZE = 4 * 1024 * 1024


async def pull_file_from_remote(
    src_url: AnyUrl,
    dst_path: Path,
    log_publishing_cb: LogPublishingCB,
    **storage_kwargs,
) -> None:
    await log_publishing_cb(
        f"Downloading '{src_url.path.strip('/')}' into local file '{dst_path.name}'..."
    )
    if not dst_path.parent.exists():
        raise ValueError(
            f"{dst_path.parent=} does not exist. It must be created by the caller"
        )

    src_mime_type, _ = mimetypes.guess_type(f"{src_url.path}")
    dst_mime_type, _ = mimetypes.guess_type(dst_path)

    open_file = fsspec.open(src_url, mode="rb", **storage_kwargs)

    def _streamer(src_fp, dst_fp):
        data = src_fp.read(CHUNK_SIZE)
        segment_len = dst_fp.write(data)
        return (data, segment_len)

    with open_file as src_fp:
        file_size = getattr(src_fp, "size", None)
        with dst_path.open("wb") as dst_fp:
            data_read = True
            while data_read:
                (
                    data_read,
                    data_written,
                ) = await asyncio.get_event_loop().run_in_executor(
                    None, _streamer, src_fp, dst_fp
                )
                await log_publishing_cb(
                    f"Downloading '{src_url.path.strip('/')}':"
                    f" {100.0 * float(data_written or 0)/float(file_size or 1):.1f}%"
                    f" ({ByteSize(data_written).human_readable() if data_written else 0} / {ByteSize(file_size).human_readable() if file_size else 'NaN'})"
                )

    await log_publishing_cb(
        f"Download of '{src_url.path.strip('/')}' into local file '{dst_path.name}' complete."
    )

    if src_mime_type == "application/zip" and dst_mime_type != "application/zip":
        await log_publishing_cb(f"Uncompressing '{dst_path.name}'...")
        logger.debug("%s is a zip file and will be now uncompressed", dst_path)
        with zipfile.ZipFile(dst_path, "r") as zip_obj:
            await asyncio.get_event_loop().run_in_executor(
                None, zip_obj.extractall, dst_path.parents[0]
            )
        # finally remove the zip archive
        await log_publishing_cb(f"Uncompressing '{dst_path.name}' complete.")
        dst_path.unlink()


async def _push_file_to_http_link(
    file_to_upload: Path, dst_url: AnyUrl, log_publishing_cb: LogPublishingCB
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


async def _push_file_to_s3_remote(
    file_to_upload: Path,
    dst_url: AnyUrl,
    log_publishing_cb: LogPublishingCB,
    **s3_kwargs,
):
    logger.debug("Uploading %s to %s...", file_to_upload, dst_url)
    fs = fsspec.filesystem(
        protocol=dst_url.scheme,
        key=s3_kwargs.get("key"),
        secret=s3_kwargs.get("secret"),
        token=s3_kwargs.get("token"),
        use_ssl=s3_kwargs.get("use_ssl", True),
        client_kwargs=s3_kwargs.get("client_kwargs"),
        # asynchronous=True
    )
    await asyncio.get_event_loop().run_in_executor(
        None,
        functools.partial(
            fs.put_file,
            file_to_upload,
            f"{dst_url}",
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
        ),
    )


async def _push_file_to_generic_remote(
    file_to_upload: Path, dst_url: AnyUrl, log_publishing_cb: LogPublishingCB
):
    logger.debug("Uploading %s to %s...", file_to_upload, dst_url)
    fs = fsspec.filesystem(
        protocol=dst_url.scheme,
        username=dst_url.user,
        password=dst_url.password,
        port=int(dst_url.port),
        host=dst_url.host,
    )
    await asyncio.get_event_loop().run_in_executor(
        None,
        functools.partial(
            fs.put_file,
            file_to_upload,
            dst_url.path,
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
        ),
    )


async def push_file_to_remote(
    src_path: Path,
    dst_url: AnyUrl,
    log_publishing_cb: LogPublishingCB,
    **storage_kwargs,
) -> None:
    if not src_path.exists():
        raise ValueError(f"{src_path=} does not exist")

    async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
        file_to_upload = src_path

        dst_mime_type, _ = mimetypes.guess_type(f"{dst_url.path}")
        src_mime_type, _ = mimetypes.guess_type(src_path)

        if dst_mime_type == "application/zip" and src_mime_type != "application/zip":
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

        if dst_url.scheme in HTTP_FILE_SYSTEM_SCHEMES:
            logger.debug("destination is a http presigned link")
            await _push_file_to_http_link(file_to_upload, dst_url, log_publishing_cb)
        elif dst_url.scheme in S3_FILE_SYSTEM_SCHEMES:
            logger.debug("destination is a S3 link")
            await _push_file_to_s3_remote(
                file_to_upload, dst_url, log_publishing_cb, **storage_kwargs
            )
        else:
            await _push_file_to_generic_remote(
                file_to_upload, dst_url, log_publishing_cb
            )

    await log_publishing_cb(
        f"Upload of '{src_path.name}' to '{dst_url.path.strip('/')}' complete"
    )
