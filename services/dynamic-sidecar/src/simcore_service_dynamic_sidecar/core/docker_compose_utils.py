""" Wrapper around docker-compose CLI with pre-defined options


docker_compose_* coroutines are implemented such that they can only
run sequentially by this service

"""
import logging
from copy import deepcopy
from pprint import pformat
from typing import Optional

from servicelib.async_utils import run_sequentially_in_context

from .settings import ApplicationSettings
from .utils import CommandResult, async_command, write_to_tmp_file

logger = logging.getLogger(__name__)


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

        logger.info("Runs %s ...\n%s", cmd, yaml_content)

        result = await async_command(
            command=cmd,
            timeout=process_termination_timeout,
        )

        logger.info("Done %s", pformat(deepcopy(result._asdict())))
        return result


async def docker_compose_config(
    compose_spec_yaml: str, settings: ApplicationSettings, timeout: Optional[int] = None
) -> CommandResult:
    """
    Validate and view the Compose file.

    The output:
        - interpolates env vars in the compose file

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_convert/)
    [SEE compose-file](https://docs.docker.com/compose/compose-file/)
    """
    assert settings  # nosec

    result = await _write_file_and_spawn_process(
        compose_spec_yaml,
        command='docker-compose --file "{file_path}" config',
        process_termination_timeout=timeout,
    )
    return result  # type: ignore


async def docker_compose_pull(
    compose_spec_yaml: str, settings: ApplicationSettings, timeout: Optional[int] = None
) -> CommandResult:
    """
    Pulls all images required by the service.

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_pull/)
    """
    # NOTE: in the future the progress of pulling should be captured from the stdout
    result = await _write_file_and_spawn_process(
        compose_spec_yaml,
        command=f'docker-compose --project-name {settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE} --file "{{file_path}}" pull',
        process_termination_timeout=timeout,
    )
    return result  # type: ignore


async def docker_compose_up(
    compose_spec_yaml: str, settings: ApplicationSettings, timeout: Optional[int] = None
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
        command=f'docker-compose --project-name {settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE} --file "{{file_path}}" up'
        " --no-build --detach",
        process_termination_timeout=timeout,
    )
    return result  # type: ignore


async def docker_compose_restart(
    compose_spec_yaml: str, settings: ApplicationSettings, timeout: int
) -> CommandResult:
    """
    Restarts running containers (w/ a timeout)

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_restart/)
    """
    assert timeout, "timeout here is mandatory"

    result = await _write_file_and_spawn_process(
        compose_spec_yaml,
        command=(
            f'docker-compose --project-name {settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE} --file "{{file_path}}" restart'
            f" --timeout {int(timeout)}"
        ),
        process_termination_timeout=None,
    )
    return result  # type: ignore


async def docker_compose_down(
    compose_spec_yaml: str, settings: ApplicationSettings, timeout: int
) -> CommandResult:
    """
    Stops containers and removes containers, networks and volumes declared in the Compose specs file

    - Removes named volumes declared in the `volumes` section of the Compose specs file and anonymous volumes attached to containers.
    - Removes containers for services NOT defined in the Compose specs file
    - Does NOT remove images

    [SEE docker-compose](https://docs.docker.com/engine/reference/commandline/compose_down/)
    """
    assert timeout, "timeout here is mandatory"

    result = await _write_file_and_spawn_process(
        compose_spec_yaml,
        command=(
            f'docker-compose --project-name {settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE} --file "{{file_path}}" down'
            f" --volumes --remove-orphans --timeout {int(timeout)}"
        ),
        process_termination_timeout=None,
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
            f'docker-compose --project-name {settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE} --file "{{file_path}}" rm'
            " --force -v"
        ),
        process_termination_timeout=None,
    )
    return result  # type: ignore
