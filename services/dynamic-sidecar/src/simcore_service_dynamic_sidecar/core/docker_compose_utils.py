import logging
from typing import Optional

from .settings import DynamicSidecarSettings
from .utils import CommandResult, async_command, write_to_tmp_file

logger = logging.getLogger(__name__)


async def _write_file_and_run_command(
    settings: DynamicSidecarSettings,
    file_content: str,
    command: str,
    command_timeout: Optional[float],
) -> CommandResult:
    """The command which accepts {file_path} as an argument for string formatting"""

    # pylint: disable=not-async-context-manager
    async with write_to_tmp_file(file_content) as file_path:
        formatted_command = command.format(
            file_path=file_path,
            project=settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE,
            stop_and_remove_timeout=settings.DYNAMIC_SIDECAR_STOP_AND_REMOVE_TIMEOUT,
        )
        logger.debug(
            "Will run command\n'%s':\n%s", f"{formatted_command=}", f"{file_content=}"
        )
        return await async_command(formatted_command, command_timeout)


#
# API
#   thin wrapper above docker-compose CLI with some
#   of the options already bound for this service's purpose
#


async def docker_compose_config(
    compose_spec_yaml: str,
    settings: DynamicSidecarSettings,
    command_timeout: float,
) -> CommandResult:
    """
    Validate and view the Compose file.

    The output:
        - interpolates env vars in the compose file
    """
    result = await _write_file_and_run_command(
        settings=settings,
        file_content=compose_spec_yaml,
        command='docker-compose --file "{file_path}" config',
        command_timeout=command_timeout,
    )
    return result


async def docker_compose_up(
    compose_spec_yaml: str, settings: DynamicSidecarSettings, command_timeout: float
) -> CommandResult:
    """
    (Re)creates, starts, and attaches to containers for a service

    - does NOT build images
    - runs in detached mode, i.e. runs containers in the background, prints new container names

    """

    command = 'docker-compose --project-name {project} --file "{file_path}" up --no-build --detach'

    result = await _write_file_and_run_command(
        settings=settings,
        file_content=compose_spec_yaml,
        command=command,
        command_timeout=command_timeout,
    )

    return result


async def docker_compose_restart(
    compose_spec_yaml: str, settings: DynamicSidecarSettings, command_timeout: float
) -> CommandResult:
    command = (
        'docker-compose --project-name {project} --file "{file_path}" '
        "restart --timeout {stop_and_remove_timeout}"
    )
    result = await _write_file_and_run_command(
        settings=settings,
        file_content=compose_spec_yaml,
        command=command,
        command_timeout=command_timeout,
    )
    return result


async def docker_compose_down(
    compose_spec_yaml: str, settings: DynamicSidecarSettings, command_timeout: float
) -> CommandResult:
    """
    Stops containers and removes containers, networks and volumes declared in the Compose specs file

    - Removes named volumes declared in the `volumes` section of the Compose specs file and anonymous volumes attached to containers.
    - Removes containers for services NOT defined in the Compose specs file
    - Does NOT remove images
    """
    command = (
        'docker-compose --project-name {project} --file "{file_path}" '
        "down --volumes --remove-orphans --timeout {stop_and_remove_timeout}"
    )
    result = await _write_file_and_run_command(
        settings=settings,
        file_content=compose_spec_yaml,
        command=command,
        command_timeout=command_timeout,
    )

    return result


async def docker_compose_rm(
    compose_spec_yaml: str, settings: DynamicSidecarSettings
) -> CommandResult:
    """
    Removes stopped service containers
        - stops the containers, if still running, before removing  (recommended to stop first)
        - removes any anonymous VOLUMES attached to containers
        - runs w/o confirmation
    """
    command = (
        'docker-compose --project-name {project} --file "{file_path}" rm --force -v'
    )
    result = await _write_file_and_run_command(
        settings=settings,
        file_content=compose_spec_yaml,
        command=command,
        command_timeout=None,
    )
    if not result.success:
        logger.warning(
            "Unexpected error while running command\n%s with %s %s:\n%s",
            f"{command=}",
            f"project={settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE}",
            f"stop_and_remove_timeout={settings.DYNAMIC_SIDECAR_STOP_AND_REMOVE_TIMEOUT}",
            f"{result.decoded_stdout}",
        )
    return result
