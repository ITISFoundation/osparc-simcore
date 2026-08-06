import logging
from pathlib import Path
from typing import Final

from aiodocker import DockerError
from aiodocker.types import JSONObject
from models_library.basic_types import PortInt
from models_library.docker import DockerLabelKey
from pydantic import ByteSize, NonNegativeInt

from ._errors import PortNotAssignedError
from ._models import DelegateInterface

_logger = logging.getLogger(__name__)

_MEMORY_SAFETY_MARGIN: Final[float] = 0.7

RC_PORT: Final[PortInt] = 8000
_DOCKER_INSPECT_NETWORK_SETTINGS_PORTS_KEY: Final[str] = f"{RC_PORT}/tcp"
_NOT_FOUND: Final[int] = 404


async def _get_config(
    delegate: DelegateInterface,
    command: str,
    r_clone_version: str,
    local_mount_path: Path,
    memory_limit: ByteSize,
    nano_cpus: NonNegativeInt,
    labels: dict[DockerLabelKey, str],
) -> JSONObject:
    return {
        "Image": f"rclone/rclone:{r_clone_version}",
        "Entrypoint": ["/bin/sh", "-c", f"{command}"],
        "Labels": labels,  # type: ignore[dict-item]
        "Env": [
            # GOMEMLIMIT sets a soft memory limit for the Go runtime garbage collector.
            # This causes more aggressive GC before hitting the container's hard memory limit.
            f"GOMEMLIMIT={int(memory_limit * _MEMORY_SAFETY_MARGIN)}",
        ],
        "ExposedPorts": {_DOCKER_INSPECT_NETWORK_SETTINGS_PORTS_KEY: {}},
        "HostConfig": {
            "PortBindings": {_DOCKER_INSPECT_NETWORK_SETTINGS_PORTS_KEY: [{"HostPort": "0"}]},
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
    labels: dict[DockerLabelKey, str],
) -> PortInt:
    container_config = await _get_config(
        delegate, command, r_clone_version, local_mount_path, memory_limit, nano_cpus, labels
    )
    _logger.debug("Creating rclone mount container '%s' with config=%s", container_name, container_config)
    await delegate.create_container(config=container_config, name=container_name)
    container_inspect = await delegate.container_inspect(container_name)
    _logger.debug(
        "Started rclone mount container '%s' with command='%s' (inspect=%s)", container_name, command, container_inspect
    )

    ports = container_inspect.get("NetworkSettings", {}).get("Ports", {})
    port_bindings = ports.get(_DOCKER_INSPECT_NETWORK_SETTINGS_PORTS_KEY)
    host_port = port_bindings[0].get("HostPort") if port_bindings else None
    if not host_port:
        raise PortNotAssignedError(
            container_name=container_name,
            target_port=_DOCKER_INSPECT_NETWORK_SETTINGS_PORTS_KEY,
            ports=ports,
        )

    return int(host_port)


async def try_inspect_r_clone_container(
    delegate: DelegateInterface,
    container_name: str,
) -> tuple[PortInt, dict[DockerLabelKey, str]] | None:
    """Inspects an existing rclone container and returns its host port and labels.

    Returns None if the container does not exist (HTTP 404).
    Re-raises any other DockerError.
    """
    try:
        existing = await delegate.container_inspect(container_name)
    except DockerError as e:
        if e.status == _NOT_FOUND:
            return None
        raise

    ports = existing.get("NetworkSettings", {}).get("Ports", {})
    port_bindings = ports.get(_DOCKER_INSPECT_NETWORK_SETTINGS_PORTS_KEY)
    host_port = port_bindings[0].get("HostPort") if port_bindings else None
    if not host_port:
        raise PortNotAssignedError(
            container_name=container_name,
            target_port=_DOCKER_INSPECT_NETWORK_SETTINGS_PORTS_KEY,
            ports=ports,
        )

    labels: dict[DockerLabelKey, str] = (existing.get("Config") or {}).get("Labels") or {}
    return int(host_port), labels
