import asyncio
from pathlib import Path
import aiohttp
import logging

from typing import Tuple

from passlib import pwd

from .async_hashing import checksum, Algorithm
from .file_response import rename

log = logging.getLogger(__name__)


def get_random_string(length: int) -> str:
    return pwd.genword(entropy=52, charset="hex")[:length]


def get_osparc_export_name(sha256_sum: str, algorithm: Algorithm) -> str:
    return f"{get_random_string(4)}#{algorithm.name}={sha256_sum}.osparc"


def validate_osparc_import_name(file_name: str) -> Tuple[Algorithm, str]:
    """returns: sha256 from file signature if present or raises an error"""
    # sample: 0a3a#SHA256=02d03b65911aae7662a8fa5fa4847d0b8f722a022d95b37b4a02960ff736853a.osparc
    if not file_name.endswith(".osparc"):
        raise aiohttp.web.HTTPException(
            reason=f"Provided file name must haave .osparc extension file_name={file_name}"
        )

    parts = file_name.replace(".osparc", "").split("#")
    if len(parts) != 2:
        raise aiohttp.web.HTTPException(
            reason=f"Could not find a digest in provided file_name={file_name}"
        )
    digest = parts[1]

    digest_parts = digest.split("=")
    if len(digest_parts) != 2:
        raise aiohttp.web.HTTPException(
            reason=f"Could not find a valid digest in provided file_name={file_name}"
        )
    algorithm, digest_sum = Algorithm[digest_parts[0]], digest_parts[1]
    return algorithm, digest_sum


def search_for_unzipped_path(search_path: Path) -> Path:
    found_dirs = []
    for path in search_path.iterdir():
        if path.is_dir():
            found_dirs.append(path)

    if len(found_dirs) != 1:
        raise aiohttp.web.HTTPException(
            reason=f"unexpected number of directories after unzipping {found_dirs}"
        )
    return search_path / found_dirs[0]


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
    osparc_formatted_name = Path(input_path.parent) / get_osparc_export_name(
        sha256_sum=sha256_sum, algorithm=Algorithm.SHA256
    )
    await rename(zip_file, osparc_formatted_name)

    return osparc_formatted_name


async def unzip_folder(input_path: Path) -> Path:
    command_args = ["unzip", str(input_path), "-d", str(input_path.parent)]

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
            reason=f"Could not decompress {str(input_path)}"
        )

    return search_for_unzipped_path(input_path.parent)
