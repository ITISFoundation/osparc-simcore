import asyncio
import logging
import os
import re
import shlex
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional
import socket
import aiodocker
import aiofiles

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
async def _config_file(config: str) -> AsyncGenerator[Path, None]:
    async with tempfile.TemporaryDirectory() as d:
        async with tempfile.NamedTemporaryFile("w", dir=d) as f:
            await f.write(config)
            await f.flush()
            yield Path(f.name)


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


async def _get_container_id() -> Optional[str]:
    """if running in a container returns the container's ID else None"""
    try:
        async with aiofiles.open("/proc/1/cgroup", "rt") as cgroup_file:
            file_content: str = await cgroup_file.read()
            for line in file_content.split("\n"):
                if "pids:/docker/" in line:
                    # 13:pids:/docker/987b04bb0e7525c17be5d022d12e63c8b8aadf0661ce9a43c9fb6abfd93dc0cc
                    return line.split("pids:/docker/")[-1]
    except FileNotFoundError:
        pass

    return None


async def _get_path_on_host(container_id: Optional[str], container_path: Path) -> Path:
    """always returns the path on the host"""
    container_id: Optional[str] = await _get_container_id()
    logger.debug("%s", f"{container_id=}")
    if container_id is None:
        return container_path

    async with aiodocker.Docker() as docker_client:
        container = docker_client.containers.container(container_id)
        container_data = await container.show()
        logger.debug("%s", f"{container_data=}")
        container_root_on_host = Path(
            container_data["GraphDriver"]["Data"]["MergedDir"]
        )
        logger.debug("%s", f"{container_root_on_host=}")

    return container_root_on_host / container_path.relative_to("/")


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
    async with _config_file(r_clone_config_file_content) as config_file_path:
        source_path = local_file_path
        destination_path = Path(s3_path)
        file_name = local_file_path.name
        # FIXME: capture progress and connect progressbars or some event to inform the UI

        config_file_parent_host_path = await _get_path_on_host(config_file_path.parent)
        source_path_parent_host_path = await _get_path_on_host(source_path.parent)

        # rclone only acts upon directories, so to target a specific file
        # we must run the command from the file's directory. See below
        # example for further details:
        #
        # local_file_path=`/tmp8274wr8w/workspace.zip`
        # s3_path=`simcore/30a298ba-e0bf-11ec-96a7-02420a000029/5d204f4a-253d-4c45-96af-d7fb78bd5a79/workspace.zip`
        #
        # docker
        #   run
        #   --memory-reservation=100m
        #   --memory=1g
        #   --cpus=0.5
        #   --rm
        #   --volume
        #   /var/lib/docker/overlay2/084f7a2ec58513e93276edebe9647706f1035c78bbf734ea8b2be99061fc6a84/merged/tmp/tmp6xetjtw9:/tmp
        #   --volume
        #   /var/lib/docker/overlay2/084f7a2ec58513e93276edebe9647706f1035c78bbf734ea8b2be99061fc6a84/merged/tmp/tmp8274wr8w:/data
        #   --user
        #   1001:7
        #   rclone/rclone:1.58.1
        #   --config
        #   /tmp/tmpqixh9_rj
        #   sync
        #   /data
        #   dst:simcore/30a298ba-e0bf-11ec-96a7-02420a000029/5d204f4a-253d-4c45-96af-d7fb78bd5a79
        #   --progress
        #   --use-mmap
        #   --transfers
        #   1
        #   --checkers
        #   1
        #   --copy-links
        #   --include
        #   workspace.zip

        r_clone_command = [
            "docker",
            "run",
            f"--memory-reservation={r_clone_settings.R_CLONE_MEMORY_RESERVATION}",
            f"--memory={r_clone_settings.R_CLONE_MEMORY_LIMIT}",
            f"--cpus={r_clone_settings.R_CLONE_MAX_CPU_USAGE}",
            "--rm",
            "--volume",
            f"{config_file_parent_host_path}:/tmp",
            "--volume",
            f"{shlex.quote(f'{source_path_parent_host_path}')}:/data",
            "--user",
            f"{os.getuid()}:{os.getpid()}",
            f"rclone/rclone:{r_clone_settings.R_CLONE_VERSION}",
            "--config",
            f"/tmp/{config_file_path.name}",
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
