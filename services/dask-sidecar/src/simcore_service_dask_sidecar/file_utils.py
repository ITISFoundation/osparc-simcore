import zipfile
from pathlib import Path

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
        async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
            if Path(URL(dst_url).path).suffix == ".zip" and src_path.suffix != ".zip":
                logger.debug("detected destination is a zip, compressing %s", src_path)

                compressed_dest_file = Path(tmp_dir) / Path(URL(dst_url).path).name
                with zipfile.ZipFile(
                    compressed_dest_file,
                    "w",
                    compression=zipfile.ZIP_DEFLATED,
                ) as zf:
                    zf.write(src_path, "logs.dat")
                logger.debug("compression to %s done", compressed_dest_file)

                file_to_upload = compressed_dest_file

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
