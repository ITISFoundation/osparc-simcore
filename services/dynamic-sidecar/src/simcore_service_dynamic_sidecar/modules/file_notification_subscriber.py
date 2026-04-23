import functools
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Final

from fastapi import FastAPI
from models_library.projects_nodes_io import StorageFileID
from models_library.rabbitmq_messages import FileNotificationEventType, FileNotificationMessage
from servicelib.container_utils import run_command_in_container
from servicelib.logging_utils import log_context
from servicelib.progress_bar import ProgressBarData
from servicelib.rabbitmq import RabbitMQClient
from simcore_sdk.node_ports_common import filemanager
from simcore_sdk.node_ports_common.constants import SIMCORE_LOCATION
from simcore_sdk.node_ports_common.r_clone_mount import NoMountFoundForRemotePathError

from ..core.rabbitmq import get_rabbitmq_client
from ..core.settings import ApplicationSettings
from ..modules.mounted_fs import MountedVolumes
from ..modules.r_clone_mount_manager import get_r_clone_mount_manager

_logger = logging.getLogger(__name__)

_MIN_STORAGE_PATH_PARTS: Final[int] = 3
_TIMEOUT_REMOVAL: Final[timedelta] = timedelta(seconds=5)


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
        command=["rm", "-rf", f"{local_path}"],
        timeout=_TIMEOUT_REMOVAL.total_seconds(),
    )
    _logger.info("Removed '%s' from disk volume (no rclone mount found)", local_path)


async def _try_pull_to_disk_volumes(
    app: FastAPI,
    mounted_volumes: MountedVolumes,
    path: StorageFileID,
) -> None:
    """Downloads a file from S3 to the corresponding local disk volume."""
    local_path = _resolve_local_path_from_storage_id(mounted_volumes, path)
    if local_path is None:
        return

    settings: ApplicationSettings = app.state.settings
    local_path.parent.mkdir(parents=True, exist_ok=True)

    async with ProgressBarData(
        num_steps=1,
        description=f"pulling {path}",
    ) as progress_bar:
        await filemanager.download_path_from_s3(
            user_id=settings.DY_SIDECAR_USER_ID,
            store_id=SIMCORE_LOCATION,
            store_name=None,
            s3_object=path,
            local_path=local_path.parent,
            io_log_redirect_cb=None,
            r_clone_settings=settings.DY_SIDECAR_R_CLONE_SETTINGS,
            progress_bar=progress_bar,
        )
    _logger.info("Pulled '%s' from S3 to disk volume", path)


async def _notify_path_change(
    app: FastAPI, *, event_type: FileNotificationEventType, path: StorageFileID, recursive: bool
) -> None:
    """
    Informs that a path inside S3 changed and that an action needs to be taken in the container.
    """
    try:
        await get_r_clone_mount_manager(app).refresh_path(f"{Path(path).parent}", recursive=recursive)
    except NoMountFoundForRemotePathError:
        mounted_volumes: MountedVolumes = app.state.mounted_volumes
        match event_type:
            case FileNotificationEventType.FILE_UPLOADED:
                await _try_pull_to_disk_volumes(app, mounted_volumes, path)
            case FileNotificationEventType.FILE_DELETED:
                await _try_remove_from_disk_volumes(mounted_volumes, path)
            case _:
                _logger.warning("Received unsupported event type '%s' for path '%s'", event_type, path)


async def _handle_file_notification(app: FastAPI, data: bytes) -> bool:
    message = FileNotificationMessage.model_validate_json(data)
    _logger.debug("Received file notification: %s for file_id=%s", message.event_type, message.file_id)
    await _notify_path_change(app=app, event_type=message.event_type, path=message.file_id, recursive=False)
    return True


def setup_file_notification_subscriber(app: FastAPI) -> None:
    async def _startup() -> None:
        settings: ApplicationSettings = app.state.settings
        topic = f"{settings.DY_SIDECAR_PROJECT_ID}.{settings.DY_SIDECAR_NODE_ID}"
        app.state.file_notification_queue = None

        with log_context(_logger, logging.INFO, msg=f"subscribing to file notifications with topic={topic}"):
            rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
            subscribed_queue, _ = await rabbit_client.subscribe(
                FileNotificationMessage.get_channel_name(),
                message_handler=functools.partial(_handle_file_notification, app),
                exclusive_queue=True,
                topics=[topic],
            )
            app.state.file_notification_queue = subscribed_queue

    async def _stop() -> None:
        queue_name: str | None = app.state.file_notification_queue
        with log_context(_logger, logging.INFO, msg=f"unsubscribing from file notifications with queue={queue_name}"):
            rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
            if queue_name is not None:
                await rabbit_client.unsubscribe(queue_name)

    app.router.on_startup.append(_startup)
    app.router.on_shutdown.append(_stop)
