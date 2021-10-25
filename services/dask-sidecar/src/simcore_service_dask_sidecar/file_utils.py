import asyncio
from pathlib import Path
from shutil import make_archive

import aiofiles
import fsspec
from pydantic.networks import AnyUrl
from yarl import URL

from .dask_utils import create_dask_worker_logger

logger = create_dask_worker_logger(__name__)


async def copy_file_to_remote(src_path: Path, dst_url: AnyUrl) -> None:
    logger.debug("copying '%s' to remote in '%s'", src_path, dst_url)
    if dst_url.scheme == "http":
        file_to_upload = src_path
        logger.debug("detected http presigned link! Uploading...")
        if Path(URL(dst_url).path).suffix == ".zip" and src_path.suffix != ".zip":
            logger.debug("detected destination is a zip, compressing %s", src_path)
            async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
                archive_file = await asyncio.get_event_loop().run_in_executor(
                    None,
                    make_archive,
                    Path(URL(dst_url).path).stem,
                    "zip",
                    tmp_dir,
                    src_path,
                    logger,
                )
                logger.debug("compression to %s done", tmp_dir)
                archive_file = Path(archive_file)
                assert archive_file.exists  # no sec
                file_to_upload = archive_file

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
        logger.debug("Uploading...")
        async with aiofiles.open(src_path, "rb") as src:
            with fsspec.open(f"{dst_url}", "wb", compression="infer") as dst:
                dst.write(await src.read())
    logger.debug("Upload complete")
