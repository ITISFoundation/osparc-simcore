""" Wrapper around docker-compose CLI with pre-defined options


docker_compose_* coroutines are implemented such that they can only
run sequentially by this service

"""
import logging
from copy import deepcopy
from pprint import pformat
from typing import Optional

from servicelib.async_utils import run_sequentially_in_context
from settings_library.basic_types import LogLevel

from .settings import ApplicationSettings
from .utils import CommandResult, async_command, write_to_tmp_file

logger = logging.getLogger(__name__)


def _docker_compose_options_from_settings(settings: ApplicationSettings) -> str:
    options = []
    if settings.LOG_LEVEL == LogLevel.DEBUG:
        options.append("--verbose")
    return " ".join(options)


def _increase_timeout(docker_command_timeout: Optional[int]) -> Optional[int]:
    if docker_command_timeout is None:
        return None
    # NOTE: ensuring process has enough time to end
    return docker_command_timeout * 10


@run_sequentially_in_context()
async def _write_file_and_spawn_process(
    yaml_content: str,
    *,
    command: str,
    process_termination_timeout: Optional[int],
) -> CommandResult:
    """The command which accepts {file_path} as an argument for string formatting

    ALL docker_compose run sequentially

    This calls is intentionally verbose at INFO level
    """
    async with write_to_tmp_file(yaml_content) as file_path:
        cmd = command.format(file_path=file_path)

        logger.debug("Runs %s ...\n%s", cmd, yaml_content)

        result = await async_command(
            command=cmd,
            timeout=process_termination_timeout,
        )

        logger.debug("Done %s", pformat(deepcopy(result._asdict())))
        return result


async def docker_compose_config(
    compose_spec_yaml: str, *, timeout: int = 60
) -> CommandResult:
    """
    Validate and view the Compose file.

    The output:
        - interpolates env vars in the compose file

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_convert/)
    [SEE compose-file](https://docs.docker.com/compose/compose-file/)
    """
    result = await _write_file_and_spawn_process(
        compose_spec_yaml,
        command='docker-compose --file "{file_path}" config',
        process_termination_timeout=timeout,
    )
    return result  # type: ignore


async def docker_compose_pull(
    compose_spec_yaml: str, settings: ApplicationSettings
) -> CommandResult:
    """
    Pulls all images required by the service.

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_pull/)
    """
    # TODO: should replace this one with the aiodocker version,
    # can easily get progress out of it and report it back to the UI
    result = await _write_file_and_spawn_process(
        compose_spec_yaml,
        command=f'docker-compose {_docker_compose_options_from_settings(settings)} --project-name {settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE} --file "{{file_path}}" pull',
        process_termination_timeout=None,
    )
    return result  # type: ignore


async def docker_compose_create(
    compose_spec_yaml: str, settings: ApplicationSettings
) -> CommandResult:
    """
    (Re)creates, starts, and attaches to containers for a service

    - does NOT build images
    - runs in DETACHED mode, i.e. runs containers in the background, prints new container names

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_up/)
    """
    # building is a security risk hence is disabled via "--no-build" parameter
    result = await _write_file_and_spawn_process(
        compose_spec_yaml,
        command=f'docker-compose {_docker_compose_options_from_settings(settings)} --project-name {settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE} --file "{{file_path}}" up'
        " --no-build --no-start",
        process_termination_timeout=None,
    )
    return result  # type: ignore


async def docker_compose_start(
    compose_spec_yaml: str, settings: ApplicationSettings
) -> CommandResult:
    """
    Starts, existing containers

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_start/)
    """
    result = await _write_file_and_spawn_process(
        compose_spec_yaml,
        command=f'docker-compose {_docker_compose_options_from_settings(settings)} --project-name {settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE} --file "{{file_path}}" start',
        process_termination_timeout=None,
    )
    return result  # type: ignore


async def docker_compose_restart(
    compose_spec_yaml: str, settings: ApplicationSettings
) -> CommandResult:
    """
    Restarts running containers (w/ a timeout)

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_restart/)
    """
    default_compose_restart_timeout = 10

    result = await _write_file_and_spawn_process(
        compose_spec_yaml,
        command=(
            f'docker-compose {_docker_compose_options_from_settings(settings)} --project-name {settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE} --file "{{file_path}}" restart'
            f" --timeout {default_compose_restart_timeout}"
        ),
        process_termination_timeout=_increase_timeout(default_compose_restart_timeout),
    )
    return result  # type: ignore


async def docker_compose_down(
    compose_spec_yaml: str, settings: ApplicationSettings
) -> CommandResult:
    """
    Stops containers and removes containers, networks and volumes declared in the Compose specs file

    - Removes named volumes declared in the `volumes` section of the Compose specs file and anonymous volumes attached to containers.
    - Removes containers for services NOT defined in the Compose specs file
    - Does NOT remove images

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_down/)
    """
    default_compose_down_timeout = 10

    result = await _write_file_and_spawn_process(
        compose_spec_yaml,
        command=(
            f'docker-compose {_docker_compose_options_from_settings(settings)} --project-name {settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE} --file "{{file_path}}" down'
            f" --volumes --remove-orphans --timeout {default_compose_down_timeout}"
        ),
        process_termination_timeout=_increase_timeout(default_compose_down_timeout),
    )
    return result  # type: ignore


async def docker_compose_rm(
    compose_spec_yaml: str, settings: ApplicationSettings
) -> CommandResult:
    """
    Removes stopped service containers
        - stops the containers, if still running, before removing  (recommended to stop first)
        - removes any anonymous VOLUMES attached to containers
        - runs w/o confirmation

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_rm)
    """
    result = await _write_file_and_spawn_process(
        compose_spec_yaml,
        command=(
            f'docker-compose {_docker_compose_options_from_settings(settings)} --project-name {settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE} --file "{{file_path}}" rm'
            " --force -v"
        ),
        process_termination_timeout=None,
    )
    return result  # type: ignore
