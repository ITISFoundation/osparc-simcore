from pathlib import Path

import aiofiles
import fsspec
from pydantic.networks import AnyUrl
from servicelib.archiving_utils import archive_dir
from yarl import URL

from .dask_utils import create_dask_worker_logger

logger = create_dask_worker_logger(__name__)


async def copy_file_to_remote(src_path: Path, dst_url: AnyUrl) -> None:
    logger.debug("copying '%s' to remote in '%s'", src_path, dst_url)
    async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
        file_to_upload = src_path
        if Path(URL(dst_url).path).suffix == ".zip" and src_path.suffix != ".zip":
            archive_file_path = Path(tmp_dir) / Path(URL(dst_url).path).name
            logger.debug("src shall be zipped into %s", archive_file_path)
            await archive_dir(
                dir_to_compress=src_path,
                destination=archive_file_path,
                compress=False,
                store_relative_path=False,
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
            logger.debug("Uploading...")
            async with aiofiles.open(file_to_upload, "rb") as src:
                with fsspec.open(f"{dst_url}", "wb", compression="infer") as dst:
                    dst.write(await src.read())
    logger.debug("Upload complete")
