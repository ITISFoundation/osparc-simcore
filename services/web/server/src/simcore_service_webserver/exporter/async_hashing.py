# inspired by by https://github.com/shash873/simple-file-checksum/

import asyncio
import logging

from enum import Enum
from pathlib import Path
from aiohttp import web

log = logging.getLogger(__name__)


class Algorithm(Enum):
    """Maps openssl supported algorighms with produced output size"""

    MD5 = 32
    SHA1 = 40
    SHA256 = 64
    SHA384 = 96
    SHA512 = 128


async def checksum(file_path: Path, algorithm=Algorithm.SHA256) -> str:
    """Calls underlying openssl for hashing"""

    str_file_path = str(file_path)
    if not file_path.is_file():
        raise web.HTTPException(reason=f"Provided path '{str_file_path}' is not a file")

    command_args = ["openssl", "dgst", f"-{algorithm.name}", str_file_path]
    proc = await asyncio.create_subprocess_exec(
        *command_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    decoded_stdout = stdout.decode()

    if proc.returncode != 0:
        log.warning("STDOUT: %s", decoded_stdout)
        log.warning("STDERR: %s", stderr.decode())
        raise web.HTTPException(
            reason=f"Could not digest with algorithm={algorithm.name} of file={str_file_path}"
        )

    digest: str = decoded_stdout.strip().split(" ")[-1]
    if len(digest) != algorithm.value:
        raise web.HTTPException(
            reason=(
                f"Expected digest len={algorithm.value} for algorithm={algorithm.name}"
                f", got len={len(digest)} for digest={digest}"
            )
        )

    return digest
