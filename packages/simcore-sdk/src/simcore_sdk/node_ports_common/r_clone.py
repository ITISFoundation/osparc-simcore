import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Optional
from uuid import uuid4

import aiodocker
import aiofiles
from aiofiles import tempfile
from aiohttp import ClientSession
from models_library.services_resources import GIGA
from models_library.users import UserID
from settings_library.r_clone import RCloneSettings, docker_size_as_bytes
from settings_library.utils_r_clone import get_r_clone_config

from .constants import SIMCORE_LOCATION
from .storage_client import LinkType, get_upload_file_link

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _config_file(config: str) -> AsyncGenerator[Path, None]:
    async with tempfile.TemporaryDirectory() as d:
        async with tempfile.NamedTemporaryFile("w", dir=d) as f:
            await f.write(config)
            await f.flush()
            yield Path(f.name)


async def _inspect_container(
    docker_client: aiodocker.Docker,
) -> Optional[dict[str, Any]]:
    """if running in a container returns the container's ID else None"""
    try:
        async with aiofiles.open("/proc/1/cgroup", "rt") as cgroup_file:
            file_content: str = await cgroup_file.read()
            for line in file_content.split("\n"):
                if "pids:/docker/" in line:
                    # 13:pids:/docker/987b04bb0e7525c17be5d022d12e63c8b8aadf0661ce9a43c9fb6abfd93dc0cc
                    container_id = line.split("pids:/docker/")[-1]
                    container = docker_client.containers.container(container_id)
                    container_inspect = await container.show()
                    return container_inspect
    except FileNotFoundError:
        pass

    return None


async def _get_path_on_host(
    container_inspect: Optional[dict[str, Any]], container_path: Path
) -> Path:
    """always returns the real path on the host, even when running in a docker container"""
    if container_inspect is None:
        return container_path

    # NOTE: trying to map from container space to HOST space
    # the file is either present on one of the Mounts
    # the file is present inside the container's file system

    # is file coming from a mount?
    container_path_str = f"{container_path}"
    for mount in container_inspect["Mounts"]:
        logger.debug("%s startswith %s", container_path_str, mount["Destination"])
        if container_path_str.startswith(mount["Destination"]):
            destination_path = Path(mount["Destination"])
            return Path(mount["Source"]) / container_path.relative_to(destination_path)

    # we assume the file is placed on the container's root fs (only available place remaining)
    container_root_on_host = Path(container_inspect["GraphDriver"]["Data"]["MergedDir"])
    logger.debug("%s", f"{container_root_on_host=}")
    return container_root_on_host / container_path.relative_to("/")


def _guess_container_name() -> Optional[str]:
    # If used inside a dynamic sidecar it tries to guess a name that
    # resembles dy-sidecar and dy-proxy... in the container's list
    if node_id := os.environ.get("DY_SIDECAR_NODE_ID"):
        random_tail: int = uuid4().time_mid
        return f"dy-rclone-{node_id}-{random_tail}"
    return None


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
    container_name = _guess_container_name()

    logger.debug(
        "Spawming r-clone container [%s] for %s; %s",
        f"{container_name=}",
        f"{s3_link=}",
        f"{s3_path=}, ",
    )

    async with _config_file(
        get_r_clone_config(r_clone_settings)
    ) as config_file_path, aiodocker.Docker() as docker_client:
        source_path = local_file_path.resolve()  # follows symlinks
        destination_path = Path(s3_path)
        file_name = source_path.name

        container_inspect: Optional[dict[str, Any]] = await _inspect_container(
            docker_client
        )
        config_file_parent_host_path = await _get_path_on_host(
            container_inspect, config_file_path.parent
        )
        source_path_parent_host_path = await _get_path_on_host(
            container_inspect, source_path.parent
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
                        "Target": "/rclone_config",
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
                f"/rclone_config/{config_file_path.name}",
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
            # FIXME: evaluate using events to detect when the container exits
            container = await docker_client.containers.run(
                container_run_config, name=container_name
            )
            try:
                for _ in range(r_clone_settings.R_CLONE_UPLOAD_TIMEOUT_S):
                    container_inspect = await container.show()
                    container_status = container_inspect["State"]["Status"]
                    if container_status != "running":
                        exit_code = container_inspect["State"]["ExitCode"]
                        if exit_code == 0:
                            break

                        logs = "\n".join(
                            x for x in await container.log(stdout=True, stderr=True)
                        )
                        logger.warning(
                            "Run logs:\n%s\n%s",
                            f"{logs}",
                            json.dumps(container_inspect, indent=2),
                        )
                        raise RuntimeError(json.dumps(container_inspect["State"]))

                    await asyncio.sleep(1)

            finally:
                await container.delete(v=True, force=True)
        except (aiodocker.DockerError, RuntimeError) as error:
            logger.warning(
                "There was an error while uploading %s. Removing metadata", s3_object
            )
            # FIXME: ANE Not a good idea, needs some rethinking in case of error
            # await delete_file(
            #     session=session,
            #     file_id=s3_object,
            #     location_id=store_id,
            #     user_id=user_id,
            # )
            raise error
