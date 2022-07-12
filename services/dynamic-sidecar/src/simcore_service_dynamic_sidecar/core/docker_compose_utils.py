""" Wrapper around docker-compose CLI with pre-defined options


"""
import logging
from typing import Optional

from .settings import DynamicSidecarSettings
from .utils import CommandResult, async_command, write_to_tmp_file

logger = logging.getLogger(__name__)


async def _write_file_and_run_command(
    settings: DynamicSidecarSettings,
    compose_spec_yaml_content: str,
    command: str,
    terminate_process_on_timeout: Optional[int],
) -> CommandResult:
    """The command which accepts {file_path} as an argument for string formatting"""

    # pylint: disable=not-async-context-manager
    async with write_to_tmp_file(compose_spec_yaml_content) as file_path:
        cmd = command.format(
            file_path=file_path,
            project=settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE,
        )
        logger.debug("Running '%s' w/ compose-spec\n%s", cmd, compose_spec_yaml_content)
        return await async_command(cmd, terminate_process_on_timeout)


async def docker_compose_config(
    compose_spec_yaml: str,
    settings: DynamicSidecarSettings,
    timeout: int,
) -> CommandResult:
    """
    Validate and view the Compose file.

    The output:
        - interpolates env vars in the compose file

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_convert/)
    [SEE compose-file](https://docs.docker.com/compose/compose-file/)
    """

    result = await _write_file_and_run_command(
        settings,
        compose_spec_yaml,
        command='docker-compose --file "{file_path}" config',
        terminate_process_on_timeout=timeout,
    )
    return result


async def docker_compose_up(
    compose_spec_yaml: str, settings: DynamicSidecarSettings, timeout: int
) -> CommandResult:
    """
    (Re)creates, starts, and attaches to containers for a service

    - does NOT build images
    - runs in DETACHED mode, i.e. runs containers in the background, prints new container names

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_up/)
    """

    result = await _write_file_and_run_command(
        settings,
        compose_spec_yaml,
        command='docker-compose --project-name {project} --file "{file_path}" up'
        " --no-build --detach",
        terminate_process_on_timeout=timeout,
    )
    return result


async def docker_compose_restart(
    compose_spec_yaml: str, settings: DynamicSidecarSettings, timeout: int
) -> CommandResult:
    """
    Restarts running containers (w/ a timeout)

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_restart/)
    """

    result = await _write_file_and_run_command(
        settings,
        compose_spec_yaml,
        command=(
            'docker-compose --project-name {project} --file "{file_path}" restart'
            f" --timeout {int(timeout)}"
        ),
        terminate_process_on_timeout=None,
    )
    return result


async def docker_compose_down(
    compose_spec_yaml: str, settings: DynamicSidecarSettings, timeout: int
) -> CommandResult:
    """
    Stops containers and removes containers, networks and volumes declared in the Compose specs file

    - Removes named volumes declared in the `volumes` section of the Compose specs file and anonymous volumes attached to containers.
    - Removes containers for services NOT defined in the Compose specs file
    - Does NOT remove images

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_down/)
    """

    result = await _write_file_and_run_command(
        settings,
        compose_spec_yaml,
        command=(
            'docker-compose --project-name {project} --file "{file_path}" down'
            f" --volumes --remove-orphans --timeout {int(timeout)}"
        ),
        terminate_process_on_timeout=None,
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

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_rm)
    """

    result = await _write_file_and_run_command(
        settings,
        compose_spec_yaml,
        command=(
            'docker-compose --project-name {project} --file "{file_path}" rm'
            " --force -v"
        ),
        terminate_process_on_timeout=None,
    )
    return result
