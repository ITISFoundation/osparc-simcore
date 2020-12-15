import asyncio
from pathlib import Path
import aiohttp
import logging

log = logging.getLogger(__name__)


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

    return zip_file
