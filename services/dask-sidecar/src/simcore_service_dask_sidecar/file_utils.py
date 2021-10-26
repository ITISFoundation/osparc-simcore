import asyncio
import mimetypes
import zipfile
from pathlib import Path

import aiofiles
import fsspec
from pydantic.networks import AnyUrl
from yarl import URL

from .dask_utils import create_dask_worker_logger

logger = create_dask_worker_logger(__name__)


async def pull_file_from_remote(src_url: AnyUrl, dst_path: Path) -> None:
    logger.debug("pulling '%s' to local destination '%s'", src_url, dst_path)
    src_mime_type, _ = mimetypes.guess_type(f"{src_url}")
    dst_mime_type, _ = mimetypes.guess_type(dst_path)

    fs = fsspec.filesystem(
        protocol=src_url.scheme,
        username=src_url.user,
        password=src_url.password,
        port=int(src_url.port),
        host=src_url.host,
    )
    await asyncio.get_event_loop().run_in_executor(
        None, fs.get_file, src_url.path, dst_path
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


async def copy_file_to_remote(src_path: Path, dst_url: AnyUrl) -> None:
    logger.debug("copying '%s' to remote in '%s'", src_path, dst_url)
    async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
        file_to_upload = src_path

        if Path(URL(dst_url).path).suffix == ".zip" and src_path.suffix != ".zip":
            archive_file_path = Path(tmp_dir) / Path(URL(dst_url).path).name
            logger.debug("src %s shall be zipped into %s", src_path, archive_file_path)
            with zipfile.ZipFile(archive_file_path, mode="w") as zfp:
                await asyncio.get_event_loop().run_in_executor(
                    None, zfp.write, src_path, src_path.name
                )
            logger.debug("%s created.", archive_file_path)
            file_to_upload = archive_file_path

        if dst_url.scheme == "http":
            file_to_upload = src_path
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
