import logging
from pathlib import Path
from typing import Final

from aiodocker.types import JSONObject
from models_library.basic_types import PortInt
from pydantic import ByteSize, NonNegativeInt

from ._errors import PortNotAssignedError
from ._models import DelegateInterface

_logger = logging.getLogger(__name__)

_MEMORY_SAFETY_MARGIN: Final[float] = 0.7

_TARGET_PORT: Final[str] = "8000/tcp"


async def _get_config(
    delegate: DelegateInterface,
    command: str,
    r_clone_version: str,
    local_mount_path: Path,
    memory_limit: ByteSize,
    nano_cpus: NonNegativeInt,
) -> JSONObject:
    return {
        "Image": f"rclone/rclone:{r_clone_version}",
        "Entrypoint": ["/bin/sh", "-c", f"{command}"],
        "Env": [
            # GOMEMLIMIT sets a soft memory limit for the Go runtime garbage collector.
            # This causes more aggressive GC before hitting the container's hard memory limit.
            f"GOMEMLIMIT={int(memory_limit * _MEMORY_SAFETY_MARGIN)}",
        ],
        "ExposedPorts": {_TARGET_PORT: {}},
        "HostConfig": {
            "PortBindings": {_TARGET_PORT: [{"HostPort": "0"}]},
            "Binds": [],
            "Mounts": await delegate.get_bind_paths(local_mount_path),
            "Devices": [{"PathOnHost": "/dev/fuse", "PathInContainer": "/dev/fuse", "CgroupPermissions": "rwm"}],
            "CapAdd": ["SYS_ADMIN"],
            "SecurityOpt": ["apparmor:unconfined", "seccomp:unconfined"],
            "MemoryReservation": memory_limit // 2,  # soft limit: reclaim aggressively
            "Memory": memory_limit,  # hard limit
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
    local_mount_path: Path,
    memory_limit: ByteSize,
    nano_cpus: NonNegativeInt,
) -> PortInt:
    container_config = await _get_config(delegate, command, r_clone_version, local_mount_path, memory_limit, nano_cpus)
    _logger.debug("Creating rclone mount container '%s' with config=%s", container_name, container_config)
    await delegate.create_container(config=container_config, name=container_name)
    container_inspect = await delegate.container_inspect(container_name)
    _logger.debug(
        "Started rclone mount container '%s' with command='%s' (inspect=%s)", container_name, command, container_inspect
    )

    ports = container_inspect.get("NetworkSettings", {}).get("Ports", {})
    port_bindings = ports.get(_TARGET_PORT)
    host_port = port_bindings[0].get("HostPort") if port_bindings else None
    if not host_port:
        raise PortNotAssignedError(
            container_name=container_name,
            target_port=_TARGET_PORT,
            ports=ports,
        )

    return int(host_port)
