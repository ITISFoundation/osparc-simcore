"""
    TODO: PC->ANE shared handlers? the most important function here is remove_the_compose_spec.
    rename this file?

"""

import logging
from typing import Optional, Tuple

from ..models.domains.shared_store import SharedStore
from .settings import DynamicSidecarSettings
from .utils import async_command, write_to_tmp_file

logger = logging.getLogger(__name__)


async def write_file_and_run_command(
    settings: DynamicSidecarSettings,
    file_content: Optional[str],
    command: str,
    command_timeout: Optional[float],
) -> Tuple[bool, str]:
    """The command which accepts {file_path} as an argument for string formatting"""

    # pylint: disable=not-async-context-manager
    async with write_to_tmp_file(file_content) as file_path:
        formatted_command = command.format(
            file_path=file_path,
            project=settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE,
            stop_and_remove_timeout=settings.DYNAMIC_SIDECAR_STOP_AND_REMOVE_TIMEOUT,
        )
        logger.debug("Will run command\n'%s':\n%s", formatted_command, file_content)
        return await async_command(formatted_command, command_timeout)


async def remove_the_compose_spec(
    shared_store: SharedStore, settings: DynamicSidecarSettings, command_timeout: float
) -> Tuple[bool, str]:
    """ """

    stored_compose_content = shared_store.compose_spec
    if stored_compose_content is None:
        return True, "No started spec to remove was found"

    # TODO: PC->ANE: WARNING check quotes on paths. I would rather use lists instead of str for command
    command = (
        "docker-compose --project-name {project} --file {file_path} "
        "down --volumes --remove-orphans --timeout {stop_and_remove_timeout}"
    )
    result = await write_file_and_run_command(
        settings=settings,
        file_content=stored_compose_content,
        command=command,
        command_timeout=command_timeout,
    )
    # removing compose-file spec
    shared_store.compose_spec = None
    shared_store.container_names = []

    return result
