import logging
import os
from datetime import timedelta
from typing import Final

from aiodocker import DockerError
from models_library.callbacks_mapping import UserServiceCommand
from servicelib.logging_utils import log_context

from ..core.errors import (
    ContainerExecCommandFailedError,
    ContainerExecContainerNotFoundError,
    ContainerExecTimeoutError,
)
from ..models.shared_store import SharedStore
from ..modules.mounted_fs import MountedVolumes
from .container_utils import run_command_in_container

_logger = logging.getLogger(__name__)

_TIMEOUT_PERMISSION_CHANGES: Final[timedelta] = timedelta(minutes=5)


async def run_before_shutdown_actions(
    shared_store: SharedStore, before_shutdown: list[UserServiceCommand]
) -> None:
    for user_service_command in before_shutdown:
        container_name = user_service_command.service
        with log_context(
            _logger, logging.INFO, f"running before_shutdown {user_service_command}"
        ):
            try:
                await run_command_in_container(
                    shared_store.original_to_container_names[container_name],
                    command=user_service_command.command,
                    timeout=user_service_command.timeout,
                )

            except (
                ContainerExecContainerNotFoundError,
                ContainerExecCommandFailedError,
                ContainerExecTimeoutError,
                DockerError,
            ):
                _logger.warning(
                    "Could not run before_shutdown command %s in container %s",
                    user_service_command.command,
                    container_name,
                    exc_info=True,
                )


async def ensure_read_permissions_on_user_service_data(
    mounted_volumes: MountedVolumes,
) -> None:
    # Makes sure sidecar has access to all files in the user services.
    # The user could have removed read permissions form a file, which will cause an error.

    # NOTE: command runs inside self container since the user service container might not always be running
    self_container = os.environ["HOSTNAME"]
    for path_to_store in (  # apply changes to otuputs and all state folders
        *mounted_volumes.disk_state_paths_iter(),
        mounted_volumes.disk_outputs_path,
    ):
        await run_command_in_container(
            self_container,
            command=f"chmod -R o+rX '{path_to_store}'",
            timeout=_TIMEOUT_PERMISSION_CHANGES.total_seconds(),
        )
