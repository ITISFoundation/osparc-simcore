import logging
import os
from pathlib import Path
from typing import Final

from aiodocker.exceptions import DockerError
from aiodocker.types import JSONObject
from models_library.basic_types import PortInt
from pydantic import ByteSize, NonNegativeInt

from ._models import DelegateInterface

_logger = logging.getLogger(__name__)

_NOT_FOUND: Final[int] = 404
_INTERNAL_SERVER_ERROR: Final[int] = 500


def _get_self_container_id() -> str:
    # in docker the hostname is the container id
    return os.environ["HOSTNAME"]


async def _get_config(
    delegate: DelegateInterface,
    command: str,
    r_clone_version: str,
    rc_port: PortInt,
    r_clone_network_name: str,
    local_mount_path: Path,
    memory_limit: ByteSize,
    nano_cpus: NonNegativeInt,
) -> JSONObject:
    return {
        "Image": f"rclone/rclone:{r_clone_version}",
        "Entrypoint": ["/bin/sh", "-c", f"{command}"],
        "ExposedPorts": {f"{rc_port}/tcp": {}},
        "HostConfig": {
            "NetworkMode": r_clone_network_name,
            "Binds": [],
            "Mounts": await delegate.get_bind_paths(local_mount_path),
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
    delegate: DelegateInterface,
    container_name: str,
    *,
    command: str,
    r_clone_version: str,
    rc_port: PortInt,
    r_clone_network_name: str,
    local_mount_path: Path,
    memory_limit: ByteSize,
    nano_cpus: NonNegativeInt,
) -> None:
    # create rclone container attached to the network
    await delegate.create_container(
        config=await _get_config(
            delegate,
            command,
            r_clone_version,
            rc_port,
            r_clone_network_name,
            local_mount_path,
            memory_limit,
            nano_cpus,
        ),
        name=container_name,
    )
    container_inspect = await delegate.container_inspect(container_name)
    _logger.debug(
        "Started rclone mount container '%s' with command='%s' (inspect=%s)",
        container_name,
        command,
        container_inspect,
    )


async def remove_container_if_exists(delegate: DelegateInterface, container_name: str) -> None:
    try:
        await delegate.remove_container(container_name)
    except DockerError as e:
        if e.status != _NOT_FOUND:
            raise


async def create_network_and_connect_current_container(delegate: DelegateInterface, network_name: str) -> None:
    await delegate.create_network({"Name": network_name, "Attachable": True})
    await delegate.connect_container_to_network(_get_self_container_id(), network_name)


async def remove_network_if_exists(delegate: DelegateInterface, network_name: str) -> None:
    try:
        await delegate.disconnect_container_from_network(_get_self_container_id(), network_name)
    except DockerError as e:
        if (
            not (e.status == _INTERNAL_SERVER_ERROR and "is not connected to network" in e.message)
            and e.status != _NOT_FOUND
        ):
            raise

    try:
        await delegate.remove_network(network_name)
    except DockerError as e:
        if e.status != _NOT_FOUND:
            raise
