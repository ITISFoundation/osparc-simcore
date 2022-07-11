import asyncio
import logging
import re
import shlex
import urllib.parse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from aiocache import cached
from aiofiles import tempfile
from models_library.api_schemas_storage import FileUploadSchema
from pydantic.errors import PydanticErrorMixin
from settings_library.r_clone import RCloneSettings
from settings_library.utils_r_clone import get_r_clone_config

logger = logging.getLogger(__name__)


class RCloneFailedError(PydanticErrorMixin, RuntimeError):
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
        raise RCloneFailedError(command=str_cmd, stdout=decoded_stdout)

    logger.debug("'%s' result:\n%s", str_cmd, decoded_stdout)
    return decoded_stdout


@cached()
async def is_r_clone_available(r_clone_settings: Optional[RCloneSettings]) -> bool:
    """returns: True if the `rclone` cli is installed and a configuration is provided"""
    if r_clone_settings is None:
        return False
    try:
        await _async_command("rclone", "--version")
        return True
    except RCloneFailedError:
        return False


async def sync_local_to_s3(
    local_file_path: Path,
    r_clone_settings: RCloneSettings,
    upload_file_links: FileUploadSchema,
) -> None:
    """_summary_

    :raises e: RCloneFailedError
    """
    assert len(upload_file_links.urls) == 1  # nosec
    s3_link = urllib.parse.unquote(upload_file_links.urls[0])
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
        # local_file_path=`/tmp/pytest-of-silenthk/pytest-80/test_sync_local_to_s30/filee3e70682-c209-4cac-a29f-6fbed82c07cd.txt`
        # s3_path=`simcore/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-000000000002/filee3e70682-c209-4cac-a29f-6fbed82c07cd.txt`
        #
        # rclone
        #   --config
        #   /tmp/tmpd_1rtmss
        #   sync
        #   '/tmp/pytest-of-silenthk/pytest-80/test_sync_local_to_s30'
        #   'dst:simcore/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-000000000002'
        #   --progress
        #   --copy-links
        #   --include
        #   'filee3e70682-c209-4cac-a29f-6fbed82c07cd.txt'
        r_clone_command = (
            "rclone",
            "--config",
            config_file_name,
            "sync",
            shlex.quote(f"{source_path.parent}"),
            shlex.quote(f"dst:{destination_path.parent}"),
            "--progress",
            "--copy-links",
            "--include",
            shlex.quote(f"{file_name}"),
        )

        await _async_command(*r_clone_command, cwd=f"{source_path.parent}")
