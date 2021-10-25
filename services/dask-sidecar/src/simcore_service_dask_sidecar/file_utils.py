from pathlib import Path

import aiofiles
import fsspec
from pydantic.networks import AnyUrl


async def copy_file_to_remote(src_path: Path, dst_url: AnyUrl) -> None:
    if dst_url.scheme == "http":
        # NOTE: special case for http scheme when uploading. this is typically a S3 put presigned link.
        # Therefore, we need to use the http filesystem directly in order to call the put_file function.
        # writing on httpfilesystem is disabled by default.
        fs = fsspec.filesystem(
            "http",
            headers={
                "Content-Length": f"{src_path.stat().st_size}",
            },
        )
        fs.put_file(src_path, f"{dst_url}", method="PUT")
    else:
        async with aiofiles.open(src_path, "rb") as src:
            with fsspec.open(f"{dst_url}", "wb", compression="infer") as dst:
                dst.write(await src.read())
