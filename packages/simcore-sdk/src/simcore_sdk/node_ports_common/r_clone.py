import asyncio
import logging
import os
import re
import shlex
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from aiofiles import tempfile
from aiohttp import ClientSession
from models_library.users import UserID
from pydantic.errors import PydanticErrorMixin
from settings_library.r_clone import RCloneSettings
from settings_library.utils_r_clone import get_r_clone_config

from .constants import SIMCORE_LOCATION
from .storage_client import LinkType, delete_file, get_upload_file_link

logger = logging.getLogger(__name__)


class _CommandFailedException(PydanticErrorMixin, RuntimeError):
    msg_template: str = "Command {command} finished with exception:\n{stdout}"


@asynccontextmanager
async def _config_file(config: str) -> AsyncGenerator[str, None]:
    async with tempfile.NamedTemporaryFile("w") as f:
        await f.write(config)
        await f.flush()
        yield f.name


async def _async_command(*cmd: str, cwd: Optional[str] = None) -> str:
    str_cmd = " ".join(cmd)
    proc = await asyncio.create_subprocess_shell(
        str_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )

    stdout, _ = await proc.communicate()
    decoded_stdout = stdout.decode()
    if proc.returncode != 0:
        raise _CommandFailedException(command=str_cmd, stdout=decoded_stdout)

    logger.debug("%s result:\n%s", str_cmd, decoded_stdout)
    return decoded_stdout


async def sync_local_to_s3(
    session: ClientSession,
    r_clone_settings: RCloneSettings,
    s3_object: str,
    local_file_path: Path,
    user_id: UserID,
    store_id: str,
) -> None:
    """NOTE: only works with simcore location"""
    assert store_id == SIMCORE_LOCATION  # nosec

    s3_link = await get_upload_file_link(
        session=session,
        file_id=s3_object,
        location_id=store_id,
        user_id=user_id,
        link_type=LinkType.S3,
    )
    s3_path = re.sub(r"^s3://", "", s3_link)
    logger.debug(" %s; %s", f"{s3_link=}", f"{s3_path=}")

    r_clone_config_file_content = get_r_clone_config(r_clone_settings)
    async with _config_file(r_clone_config_file_content) as config_file_name:
        source_path = local_file_path
        destination_path = Path(s3_path)
        file_name = local_file_path.name
        # FIXME: capture progress and connect progressbars or some event to inform the UI

        # rclone only acts upon directories, so to target a specific file
        # we must run the command from the file's directory. See below
        # example for further details:
        #
        # local_file_path=`/tmp/pytest-20/test_sync_local_to_s3__xf6_xe40/öä$äö2-34 no extension`
        # s3_path=`simcore/e7b54a8d-61f4-4575-8e5a-343aebbeba1b/affb6e6b-83cd-442b-8a24-63a93917f6cf/öä$äö2-34 no extension`
        #
        # docker
        #   run
        #   --memory-reservation=100m
        #   --memory=1g
        #   --cpus=0.5
        #   --rm
        #   --volume
        #   /tmp/tmpekoemohu:/.rclone.conf
        #   --volume /tmp/pytest-20/test_sync_local_to_s3__xf6_xe40:/data
        #   --user
        #   1001:3083812
        #   rclone/rclone:1.58.1
        #   sync
        #   /data
        #   dst:simcore/e7b54a8d-61f4-4575-8e5a-343aebbeba1b/affb6e6b-83cd-442b-8a24-63a93917f6cf
        #   --progress
        #   --use-mmap
        #   --transfers
        #   1
        #   --checkers
        #   1
        #   --copy-links
        #   --include
        #   'öä$äö2-34 no extension'
        r_clone_command = [
            "docker",
            "run",
            f"--memory-reservation={r_clone_settings.R_CLONE_MEMORY_RESERVATION}",
            f"--memory={r_clone_settings.R_CLONE_MEMORY_LIMIT}",
            f"--cpus={r_clone_settings.R_CLONE_MAX_CPU_USAGE}",
            "--rm",
            "--volume",
            f"{config_file_name}:/.rclone.conf",
            "--volume",
            f"{shlex.quote(f'{source_path.parent}')}:/data",
            "--user",
            f"{os.getuid()}:{os.getpid()}",
            f"rclone/rclone:{r_clone_settings.R_CLONE_VERSION}",
            "sync",
            "/data",
            shlex.quote(f"dst:{destination_path.parent}"),
            "--progress",
            "--use-mmap",
            "--transfers",
            "1",
            "--checkers",
            "1",
            "--copy-links",
            "--include",
            shlex.quote(f"{file_name}"),
        ]

        try:
            await _async_command(*r_clone_command, cwd=f"{source_path.parent}")
        except Exception as e:
            logger.warning(
                "There was an error while uploading %s. Removing metadata", s3_object
            )
            await delete_file(
                session=session,
                file_id=s3_object,
                location_id=store_id,
                user_id=user_id,
            )
            raise e
