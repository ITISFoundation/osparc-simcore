"""
    TODO: PC->ANE shared handlers? the most important function here is remove_the_compose_spec.
    rename this file?

"""

import logging
from typing import Optional

from ..models.domains.shared_store import SharedStore
from .settings import DynamicSidecarSettings
from .utils import async_command, write_to_tmp_file

logger = logging.getLogger(__name__)


async def write_file_and_run_command(
    settings: DynamicSidecarSettings,
    file_content: Optional[str],
    command: str,
    command_timeout: Optional[float],
) -> tuple[bool, str]:
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
) -> tuple[bool, str]:
    """Basically  'docker-compose down'"""

    stored_compose_content = shared_store.compose_spec
    if stored_compose_content is None:
        return True, "No started spec to remove was found"

    # TODO: PC->ANE: there are safer ways to write a *validated* compose-spec and down container's compose
    # TODO: PC->ANE: --remove-orphans?? What about other running containers ?? Are you sure about this??!!!
    command = (
        "docker-compose"
        " --project-name {project}"
        ' --file "{file_path}"'
        " down"  # stops containers (also orphans) and removes containers, networks, volumes, and images created by `up`
        " --volumes"  # Remove named volumes declared in the `volumes` section of the Compose file and anonymous volumes attached to containers.
        " --remove-orphans"  # Remove containers for services not defined in the Compose file
        "--timeout {stop_and_remove_timeout}"  # Specify a shutdown timeout in seconds
    )
    result = await write_file_and_run_command(
        settings=settings,
        file_content=stored_compose_content,
        command=" ".join(command),
        command_timeout=command_timeout,
    )
    # removing compose-file spec
    shared_store.compose_spec = None
    shared_store.container_names = []

    return result
