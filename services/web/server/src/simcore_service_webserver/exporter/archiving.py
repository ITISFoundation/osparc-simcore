import asyncio
from pathlib import Path
import aiohttp
import logging

from passlib import pwd

from .async_hashing import checksum, Algorithm
from .file_response import rename

log = logging.getLogger(__name__)


def get_random_string(length: int) -> str:
    return pwd.genword(entropy=52, charset="hex")[:length]


async def zip_folder(project_id: str, input_path: Path, no_compression=False) -> Path:
    """Zips a folder and returns the path to the new archive"""

    zip_file = Path(input_path.parent) / f"{project_id}.zip"
    if zip_file.is_file():
        raise aiohttp.web.HTTPException(
            reason=f"Cannot archive because file already exists '{str(zip_file)}'"
        )

    command_args = [
        "zip",
        "-0",
        "-r",
        str(zip_file),
        project_id,
    ]
    if no_compression:
        command_args.remove("-0")

    proc = await asyncio.create_subprocess_exec(
        *command_args,
        cwd=str(input_path.parent),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        log.warning("STDOUT: %s", stdout.decode())
        log.warning("STDERR: %s", stderr.decode())
        raise aiohttp.web.HTTPException(
            reason=f"Could not create archive {str(zip_file)}"
        )

    # compute checksum and rename
    sha256_sum = await checksum(file_path=zip_file, algorithm=Algorithm.SHA256)

    # opsarc_formatted_name= "4_rand_chars#sha256_sum.osparc"
    osparc_formatted_name = (
        Path(input_path.parent) / f"{get_random_string(4)}#{sha256_sum}.osparc"
    )
    await rename(zip_file, osparc_formatted_name)

    return osparc_formatted_name
