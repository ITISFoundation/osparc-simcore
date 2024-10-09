import asyncio
import logging

from pydantic import ByteSize

_logger = logging.getLogger(__name__)


async def get_size_bash_async(path) -> ByteSize:
    # Create the subprocess
    command = ["du", "-sb", path]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Wait for the subprocess to complete
    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        # Parse the output
        size = ByteSize(stdout.decode().split()[0])
        return size
    else:
        msg = f"Command {' '.join(command)} failed with error code {process.returncode}: {stderr.decode()}"
        _logger.error(msg)
        raise RuntimeError(msg)


async def remove_write_permissions_bash_async(path) -> None:
    # Create the subprocess
    command = ["chmod", "-R", "a-w", path]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Wait for the subprocess to complete
    _, stderr = await process.communicate()

    if process.returncode == 0:
        return
    msg = f"Command {' '.join(command)} failed with error code {process.returncode}: {stderr.decode()}"
    _logger.error(msg)
    raise RuntimeError(msg)
