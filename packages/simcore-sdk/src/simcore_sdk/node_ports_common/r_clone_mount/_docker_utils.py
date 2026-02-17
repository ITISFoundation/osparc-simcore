import logging
from pathlib import Path
from typing import Final

from aiodocker.types import JSONObject
from models_library.basic_types import PortInt
from pydantic import ByteSize, NonNegativeInt

from ._models import DelegateInterface

_logger = logging.getLogger(__name__)

_MEMORY_SAFETY_MARGIN: Final[float] = 0.7


async def _get_config(
    delegate: DelegateInterface,
    command: str,
    r_clone_version: str,
    rc_port: PortInt,
    local_mount_path: Path,
    memory_limit: ByteSize,
    nano_cpus: NonNegativeInt,
) -> JSONObject:
    return {
        "Image": f"rclone/rclone:{r_clone_version}",
        "Entrypoint": ["/bin/sh", "-c", f"{command}"],
        "Env": [
            # GOMEMLIMIT sets a soft memory limit for the Go runtime garbage collector.
            # This causes rclone to GC more aggressively before hitting the container's
            # hard memory limit.
            f"GOMEMLIMIT={int(memory_limit * _MEMORY_SAFETY_MARGIN)}",
        ],
        "ExposedPorts": {"8000/tcp": {}},
        "HostConfig": {
            "PortBindings": {"8000/tcp": [{"HostPort": str(rc_port)}]},
            "Binds": [],
            "Mounts": await delegate.get_bind_paths(local_mount_path),
            "Devices": [{"PathOnHost": "/dev/fuse", "PathInContainer": "/dev/fuse", "CgroupPermissions": "rwm"}],
            "CapAdd": ["SYS_ADMIN"],
            "SecurityOpt": ["apparmor:unconfined", "seccomp:unconfined"],
            "MemoryReservation": memory_limit // 2,  # soft limit: reclaim aggressively
            "Memory": memory_limit,  # hard limit
            "MemorySwap": -1,  # allow swap as safety valve
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
    local_mount_path: Path,
    memory_limit: ByteSize,
    nano_cpus: NonNegativeInt,
) -> None:
    container_config = await _get_config(
        delegate, command, r_clone_version, rc_port, local_mount_path, memory_limit, nano_cpus
    )
    _logger.debug("Creating rclone mount container '%s' with config=%s", container_name, container_config)
    await delegate.create_container(config=container_config, name=container_name)
    container_inspect = await delegate.container_inspect(container_name)
    _logger.debug(
        "Started rclone mount container '%s' with command='%s' (inspect=%s)", container_name, command, container_inspect
    )
