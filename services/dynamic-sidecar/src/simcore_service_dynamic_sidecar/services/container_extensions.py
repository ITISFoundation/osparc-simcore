import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Final

from aiodocker.networks import DockerNetwork
from fastapi import FastAPI
from models_library.projects_nodes_io import StorageFileID
from models_library.rabbitmq_messages import FileNotificationEventType
from models_library.services import ServiceOutput
from servicelib.container_utils import run_command_in_container
from simcore_sdk.node_ports_common.r_clone_mount import NoMountFoundForRemotePathError
from simcore_sdk.node_ports_v2.port_utils import is_file_type

from ..core.docker_utils import docker_client
from ..modules.inputs import disable_inputs_pulling, enable_inputs_pulling
from ..modules.mounted_fs import MountedVolumes
from ..modules.outputs import (
    OutputsContext,
    disable_event_propagation,
    enable_event_propagation,
)
from ..modules.r_clone_mount_manager import get_r_clone_mount_manager

_logger = logging.getLogger(__name__)

_MIN_STORAGE_PATH_PARTS: Final[int] = 3
_TIMEOUT_REMOVAL: Final[timedelta] = timedelta(seconds=5)


async def toggle_ports_io(app: FastAPI, *, enable_outputs: bool, enable_inputs: bool) -> None:
    if enable_outputs:
        await enable_event_propagation(app)
    else:
        await disable_event_propagation(app)

    if enable_inputs:
        enable_inputs_pulling(app)
    else:
        disable_inputs_pulling(app)


async def create_output_dirs(app: FastAPI, *, outputs_labels: dict[str, ServiceOutput]) -> None:
    mounted_volumes: MountedVolumes = app.state.mounted_volumes
    outputs_context: OutputsContext = app.state.outputs_context

    outputs_path = mounted_volumes.disk_outputs_path
    file_type_port_keys = []
    non_file_port_keys = []
    for port_key, service_output in outputs_labels.items():
        _logger.debug("Parsing output labels, detected: %s", f"{port_key=}")
        if is_file_type(service_output.property_type):
            dir_to_create = outputs_path / port_key
            dir_to_create.mkdir(parents=True, exist_ok=True)
            file_type_port_keys.append(port_key)
        else:
            non_file_port_keys.append(port_key)

    _logger.debug("Setting: %s, %s", f"{file_type_port_keys=}", f"{non_file_port_keys=}")
    await outputs_context.set_file_type_port_keys(file_type_port_keys)
    outputs_context.non_file_type_port_keys = non_file_port_keys


async def attach_container_to_network(*, container_id: str, network_id: str, network_aliases: list[str]) -> None:
    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)
        container_inspect = await container_instance.show()

        attached_network_ids: set[str] = {
            x["NetworkID"] for x in container_inspect["NetworkSettings"]["Networks"].values()
        }

        if network_id in attached_network_ids:
            _logger.debug(
                "Container %s already attached to network %s",
                container_id,
                network_id,
            )
            return

        # NOTE: A docker network is only visible on a docker node when it is
        # used by a container
        network = DockerNetwork(docker=docker, id_=network_id)
        await network.connect(
            {
                "Container": container_id,
                "EndpointConfig": {"Aliases": network_aliases},
            }
        )


async def detach_container_from_network(*, container_id: str, network_id: str) -> None:
    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)
        container_inspect = await container_instance.show()

        attached_network_ids: set[str] = set(container_inspect["NetworkSettings"]["Networks"].keys())

        if network_id not in attached_network_ids:
            _logger.debug(
                "Container %s already detached from network %s",
                container_id,
                network_id,
            )
            return

        # NOTE: A docker network is only visible on a docker node when it is
        # used by a container
        network = DockerNetwork(docker=docker, id_=network_id)
        await network.disconnect({"Container": container_id, "Force": True})


def _resolve_local_path_from_storage_id(
    mounted_volumes: MountedVolumes,
    storage_path: StorageFileID,
) -> Path | None:
    """Maps a StorageFileID to a local disk path within mounted volumes."""
    path_parts = storage_path.split("/")
    if len(path_parts) < _MIN_STORAGE_PATH_PARTS:
        return None

    volume_name = path_parts[2]
    relative_parts = path_parts[_MIN_STORAGE_PATH_PARTS:]

    local_base: Path | None = None
    if volume_name == mounted_volumes.inputs_path.name:
        local_base = mounted_volumes.disk_inputs_path
    elif volume_name == mounted_volumes.outputs_path.name:
        local_base = mounted_volumes.disk_outputs_path
    else:
        for state_path, disk_state_path in zip(
            mounted_volumes.state_paths,
            mounted_volumes.disk_state_paths_iter(),
            strict=True,
        ):
            if volume_name == state_path.name:
                local_base = disk_state_path
                break

    if local_base is None:
        return None

    local_path = local_base / Path(*relative_parts) if relative_parts else local_base

    resolved = local_path.resolve()
    if not resolved.is_relative_to(local_base.resolve()):
        _logger.warning("Resolved path '%s' is outside volume '%s'", resolved, local_base)
        return None

    return resolved


async def _try_remove_from_disk_volumes(
    mounted_volumes: MountedVolumes,
    path: StorageFileID,
) -> None:
    """Removes the file or directory contents at the given storage path from disk volumes."""
    local_path = _resolve_local_path_from_storage_id(mounted_volumes, path)
    if local_path is None or not local_path.exists():
        return

    self_container = os.environ["HOSTNAME"]
    await run_command_in_container(
        self_container,
        command=f"rm -rf '{local_path}'",
        timeout=_TIMEOUT_REMOVAL.total_seconds(),
    )
    _logger.info("Removed '%s' from disk volume (no rclone mount found)", local_path)


async def notify_path_change(
    app: FastAPI, *, event_type: FileNotificationEventType, path: StorageFileID, recursive: bool
) -> None:
    """
    Informs that a path inside S3 changed and that an action needs to be taken in the container.
    """
    if event_type == FileNotificationEventType.FILE_DELETED:
        try:
            await get_r_clone_mount_manager(app).refresh_path(f"{Path(path).parent}", recursive=recursive)
        except NoMountFoundForRemotePathError:
            mounted_volumes: MountedVolumes = app.state.mounted_volumes
            await _try_remove_from_disk_volumes(mounted_volumes, path)
    else:
        _logger.warning("Received unsupported event type '%s' for path '%s'", event_type, path)
