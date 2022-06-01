import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiodocker
import aiofiles
from aiofiles import tempfile
from aiohttp import ClientSession
from models_library.services_resources import GIGA
from models_library.users import UserID
from settings_library.r_clone import RCloneSettings, docker_size_as_bytes
from settings_library.utils_r_clone import get_r_clone_config

from .constants import SIMCORE_LOCATION
from .storage_client import LinkType, delete_file, get_upload_file_link

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _config_file(config: str) -> AsyncGenerator[Path, None]:
    async with tempfile.TemporaryDirectory() as d:
        async with tempfile.NamedTemporaryFile("w", dir=d) as f:
            await f.write(config)
            await f.flush()
            yield Path(f.name)


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


async def _get_path_on_host(
    docker_client: aiodocker.Docker, container_path: Path
) -> Path:
    """always returns the real path on the host, even when running in a docker container"""
    container_id: Optional[str] = await _get_container_id()
    logger.debug("%s", f"{container_id=}")
    if container_id is None:
        return container_path

    container = docker_client.containers.container(container_id)
    container_data = await container.show()
    logger.debug("%s", f"{container_data=}")
    container_root_on_host = Path(container_data["GraphDriver"]["Data"]["MergedDir"])
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

    async with _config_file(
        get_r_clone_config(r_clone_settings)
    ) as config_file_path, aiodocker.Docker() as docker_client:
        source_path = local_file_path.resolve()  # follows symlinks
        destination_path = Path(s3_path)
        file_name = source_path.name

        config_file_parent_host_path = await _get_path_on_host(
            docker_client, config_file_path.parent
        )
        source_path_parent_host_path = await _get_path_on_host(
            docker_client, source_path.parent
        )

        container_run_config = {
            "HostConfig": {
                "Memory": docker_size_as_bytes(r_clone_settings.R_CLONE_MEMORY_LIMIT),
                "MemoryReservation": docker_size_as_bytes(
                    r_clone_settings.R_CLONE_MEMORY_RESERVATION
                ),
                "NanoCpus": int(r_clone_settings.R_CLONE_MAX_CPU_USAGE * GIGA),
                "Mounts": [
                    {
                        "Type": "bind",
                        "Source": f"{config_file_parent_host_path}",
                        "Target": "/tmp",
                    },
                    {
                        "Type": "bind",
                        "Source": f"{source_path_parent_host_path}",
                        "Target": "/data",
                    },
                ],
            },
            "User": f"{os.getuid()}:{os.getpid()}",
            "Image": f"rclone/rclone:{r_clone_settings.R_CLONE_VERSION}",
            "Cmd": [
                "--config",
                f"/tmp/{config_file_path.name}",
                "sync",
                "/data",
                f"dst:{destination_path.parent}",
                "--progress",
                "--use-mmap",
                "--transfers",
                "1",
                "--checkers",
                "1",
                "--include",
                f"{file_name}",
            ],
        }
        logger.debug("%s", f"{container_run_config=}")

        try:
            container = await docker_client.containers.run(container_run_config)
            try:
                for _ in range(r_clone_settings.R_CLONE_UPLOAD_TIMEOUT_S):
                    container_inspect = await container.show()
                    container_status = container_inspect["State"]["Status"]
                    # logger.debug(json.dumps(container_inspect["State"], indent=2))
                    if container_status != "running":
                        exit_code = container_inspect["State"]["ExitCode"]
                        if exit_code == 0:
                            break

                        logs = "\n".join(
                            x for x in await container.log(stdout=True, stderr=True)
                        )
                        logger.warning("Run logs:\n%s", f"{logs}")
                        raise RuntimeError(json.dumps(container_inspect["State"]))

                    await asyncio.sleep(1)

            finally:
                await container.delete(v=True, force=True)
        except (aiodocker.DockerError, RuntimeError) as error:
            logger.warning(
                "There was an error while uploading %s. Removing metadata", s3_object
            )
            await delete_file(
                session=session,
                file_id=s3_object,
                location_id=store_id,
                user_id=user_id,
            )
            raise error
