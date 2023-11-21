import logging

from models_library.callbacks_mapping import UserServiceCommand
from servicelib.logging_utils import log_context

from ..core.errors import (
    ContainerExecCommandFailedError,
    ContainerExecContainerNotFoundError,
    ContainerExecTimeoutError,
)
from ..models.shared_store import SharedStore
from ..modules.container_utils import run_command_in_container

_logger = logging.getLogger(__name__)


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
            ):
                _logger.warning(
                    "Could not run before_shutdown command %s in container %s",
                    user_service_command.command,
                    container_name,
                    exc_info=True,
                )
