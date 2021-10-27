import asyncio
import mimetypes
import zipfile
from pathlib import Path
from pprint import pformat
from typing import Final

import aiofiles
import fsspec
from pydantic.networks import AnyUrl
from yarl import URL

from .dask_utils import create_dask_worker_logger

logger = create_dask_worker_logger(__name__)

HTTP_FILE_SYSTEM_SCHEMES: Final = ["http", "https"]


async def pull_file_from_remote(src_url: AnyUrl, dst_path: Path) -> None:
    logger.debug("pulling '%s' to local destination '%s'", src_url, dst_path)
    src_mime_type, _ = mimetypes.guess_type(f"{src_url.path}")
    dst_mime_type, _ = mimetypes.guess_type(dst_path)

    filesystem_cfg = {
        "protocol": src_url.scheme,
    }
    if src_url.scheme not in HTTP_FILE_SYSTEM_SCHEMES:
        filesystem_cfg["host"] = src_url.host
        filesystem_cfg["username"] = src_url.user
        filesystem_cfg["password"] = src_url.password
        filesystem_cfg["port"] = int(src_url.port)
    logger.debug("file system configuration is %s", pformat(filesystem_cfg))
    fs = fsspec.filesystem(**filesystem_cfg)
    await asyncio.get_event_loop().run_in_executor(
        None,
        fs.get_file,
        f"{src_url.path}"
        if src_url.scheme not in HTTP_FILE_SYSTEM_SCHEMES
        else src_url,
        dst_path,
    )
    if src_mime_type == "application/zip" and dst_mime_type != "application/zip":
        logger.debug("%s is a zip file and will be now uncompressed", dst_path)
        with zipfile.ZipFile(dst_path, "r") as zip_obj:
            await asyncio.get_event_loop().run_in_executor(
                None, zip_obj.extractall, dst_path.parents[0]
            )
        # finally remove the zip archive
        logger.debug("%s uncompressed", dst_path)
        dst_path.unlink()


async def push_file_to_remote(src_path: Path, dst_url: AnyUrl) -> None:
    logger.debug("copying '%s' to remote in '%s'", src_path, dst_url)
    async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
        file_to_upload = src_path

        dst_mime_type, _ = mimetypes.guess_type(f"{dst_url.path}")
        src_mime_type, _ = mimetypes.guess_type(src_path)

        if dst_mime_type == "application/zip" and src_mime_type != "application/zip":
            archive_file_path = Path(tmp_dir) / Path(URL(dst_url).path).name
            logger.debug("src %s shall be zipped into %s", src_path, archive_file_path)
            with zipfile.ZipFile(
                archive_file_path, mode="w", compression=zipfile.ZIP_DEFLATED
            ) as zfp:
                await asyncio.get_event_loop().run_in_executor(
                    None, zfp.write, src_path, src_path.name
                )
            logger.debug("%s created.", archive_file_path)
            assert archive_file_path.exists()  # no sec
            file_to_upload = archive_file_path

        if dst_url.scheme in HTTP_FILE_SYSTEM_SCHEMES:
            logger.debug("destination is a http presigned link")
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
                file_to_upload, f"{dst_url}", method="PUT"
            )
        else:
            logger.debug("Uploading %s to %s...", file_to_upload, dst_url)
            fs = fsspec.filesystem(
                protocol=dst_url.scheme,
                username=dst_url.user,
                password=dst_url.password,
                port=int(dst_url.port),
                host=dst_url.host,
            )
            await asyncio.get_event_loop().run_in_executor(
                None, fs.put_file, file_to_upload, dst_url.path
            )

    logger.debug("Upload complete")
