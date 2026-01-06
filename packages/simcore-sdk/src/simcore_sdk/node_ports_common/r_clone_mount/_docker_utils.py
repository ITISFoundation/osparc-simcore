import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

from aiodocker import Docker
from aiodocker.exceptions import DockerError
from aiodocker.networks import DockerNetwork
from aiodocker.types import JSONObject
from models_library.basic_types import PortInt
from pydantic import ByteSize, NonNegativeInt

from ._models import GetBindPathsProtocol

_logger = logging.getLogger(__name__)

_NOT_FOUND: Final[int] = 404
_INTERNAL_SERVER_ERROR: Final[int] = 500


def _get_self_container_id() -> str:
    # in docker the hostname is the container id
    return os.environ["HOSTNAME"]


@asynccontextmanager
async def get_or_create_docker_session(docker: Docker | None) -> AsyncIterator[Docker]:
    if docker is not None:
        yield docker
        return

    async with Docker() as client:
        yield client


async def _get_config(
    command: str,
    r_clone_version: str,
    rc_port: PortInt,
    r_clone_network_name: str,
    local_mount_path: Path,
    memory_limit: ByteSize,
    nano_cpus: NonNegativeInt,
    handler_get_bind_paths: GetBindPathsProtocol,
) -> JSONObject:
    return {
        "Image": f"rclone/rclone:{r_clone_version}",
        "Entrypoint": ["/bin/sh", "-c", f"{command}"],
        "ExposedPorts": {f"{rc_port}/tcp": {}},
        "HostConfig": {
            "NetworkMode": r_clone_network_name,
            "Binds": [],
            "Mounts": await handler_get_bind_paths(local_mount_path),
            "Devices": [
                {
                    "PathOnHost": "/dev/fuse",
                    "PathInContainer": "/dev/fuse",
                    "CgroupPermissions": "rwm",
                }
            ],
            "CapAdd": ["SYS_ADMIN"],
            "SecurityOpt": ["apparmor:unconfined", "seccomp:unconfined"],
            "Memory": memory_limit,
            "MemorySwap": memory_limit,
            "NanoCpus": nano_cpus,
        },
    }


async def create_r_clone_container(
    docker: Docker | None,
    container_name: str,
    *,
    command: str,
    r_clone_version: str,
    rc_port: PortInt,
    r_clone_network_name: str,
    local_mount_path: Path,
    memory_limit: ByteSize,
    nano_cpus: NonNegativeInt,
    handler_get_bind_paths: GetBindPathsProtocol,
) -> None:
    async with get_or_create_docker_session(docker) as client:
        # create rclone container attached to the network
        r_clone_container = await client.containers.run(
            config=await _get_config(
                command,
                r_clone_version,
                rc_port,
                r_clone_network_name,
                local_mount_path,
                memory_limit,
                nano_cpus,
                handler_get_bind_paths,
            ),
            name=container_name,
        )
        container_inspect = await r_clone_container.show()
        _logger.debug(
            "Started rclone mount container '%s' with command='%s' (inspect=%s)",
            container_name,
            command,
            container_inspect,
        )


async def create_network_and_connect_sidecar_container(docker: Docker | None, network_name: str) -> None:
    async with get_or_create_docker_session(docker) as client:
        r_clone_network = await client.networks.create({"Name": network_name, "Attachable": True})
        await r_clone_network.connect({"Container": _get_self_container_id()})


async def remove_container_if_exists(docker: Docker | None, container_name: str) -> None:
    async with get_or_create_docker_session(docker) as client:
        try:
            existing_container = await client.containers.get(container_name)
            await existing_container.delete(force=True)
        except DockerError as e:
            if e.status != _NOT_FOUND:
                raise


async def remove_network_if_exists(docker: Docker | None, network_name: str) -> None:
    async with get_or_create_docker_session(docker) as client:
        existing_network = DockerNetwork(client, network_name)

        try:
            await existing_network.disconnect({"Container": _get_self_container_id()})
        except DockerError as e:
            if (
                not (e.status == _INTERNAL_SERVER_ERROR and "is not connected to network" in e.message)
                and e.status != _NOT_FOUND
            ):
                raise

        try:
            await existing_network.show()
            await existing_network.delete()
        except DockerError as e:
            if e.status != _NOT_FOUND:
                raise
