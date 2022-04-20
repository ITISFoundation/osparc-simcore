import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

import aioboto3
from aiofiles import tempfile
from cache import AsyncLRU
from settings_library.r_clone import RCloneSettings
from settings_library.utils_r_clone import get_r_clone_config

from ..node_ports_common.filemanager import ETag

logger = logging.getLogger(__name__)


class _CommandFailedException(Exception):
    pass


class RCloneError(Exception):
    pass


@asynccontextmanager
async def _config_file(config: str) -> AsyncGenerator[str, None]:
    async with tempfile.NamedTemporaryFile("w") as f:
        await f.write(config)
        await f.flush()
        yield f.name


async def _async_command(command: str, *, cwd: Optional[str] = None) -> str:
    proc = await asyncio.create_subprocess_shell(
        command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )

    stdout, _ = await proc.communicate()
    decoded_stdout = stdout.decode()
    if proc.returncode != 0:
        raise _CommandFailedException(
            f"Command {command} finished with exception:\n{decoded_stdout}"
        )

    logger.debug("'%s' result:\n%s", command, decoded_stdout)
    return decoded_stdout


@AsyncLRU(maxsize=1)
async def is_r_clone_installed(r_clone_settings: Optional[RCloneSettings]) -> bool:
    """returns: True if the `rclone` cli is installed and a configuration is provided"""
    try:
        await _async_command("rclone --version")
        return r_clone_settings is not None
    except _CommandFailedException:
        return False


async def _get_etag_via_s3(r_clone_settings: RCloneSettings, s3_path: str) -> ETag:
    session = aioboto3.Session(
        aws_access_key_id=r_clone_settings.S3_ACCESS_KEY,
        aws_secret_access_key=r_clone_settings.S3_SECRET_KEY,
    )
    async with session.resource("s3", endpoint_url=r_clone_settings.S3_ENDPOINT) as s3:
        s3_object = await s3.Object(
            bucket_name=r_clone_settings.S3_BUCKET_NAME,
            key=s3_path.lstrip(r_clone_settings.S3_BUCKET_NAME),
        )
        e_tag_result = await s3_object.e_tag
        # NOTE: above result is JSON encoded for some reason
        return json.loads(e_tag_result)


async def sync_to_s3(
    r_clone_settings: Optional[RCloneSettings], s3_path: str, local_file_path: Path
) -> ETag:
    if r_clone_settings is None:
        raise RCloneError(
            (
                f"Could not sync {local_file_path=} to {s3_path=}, provided "
                f"config is invalid{r_clone_settings=}"
            )
        )

    r_clone_config_file_content = get_r_clone_config(r_clone_settings)
    async with _config_file(r_clone_config_file_content) as config_file_name:
        source_path = local_file_path
        destination_path = Path(s3_path)
        assert local_file_path.name == destination_path.name
        file_name = local_file_path.name

        # rclone only acts upon directories, so to target a specific file
        # we must run the command from the file's directory. See below
        # example for further details:
        #
        # local_file_path=`/tmp/pytest-of-silenthk/pytest-80/test_sync_to_s30/filee3e70682-c209-4cac-a29f-6fbed82c07cd.txt`
        # s3_path=`simcore/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-000000000002/filee3e70682-c209-4cac-a29f-6fbed82c07cd.txt`
        #
        # rclone
        #   --config
        #   /tmp/tmpd_1rtmss
        #   sync
        #   '/tmp/pytest-of-silenthk/pytest-80/test_sync_to_s30'
        #   'dst:simcore/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-000000000002'
        #   --progress
        #   --include
        #   'filee3e70682-c209-4cac-a29f-6fbed82c07cd.txt'
        r_clone_command = [
            "rclone",
            "--config",
            config_file_name,
            "sync",
            f"'{source_path.parent}'",
            f"'dst:{destination_path.parent}'",
            "--progress",
            "--include",
            f"'{file_name}'",
        ]
        command_result = await _async_command(
            " ".join(r_clone_command), cwd=f"{source_path.parent}"
        )
        logger.debug(command_result)

        return await _get_etag_via_s3(
            r_clone_settings=r_clone_settings, s3_path=s3_path
        )
