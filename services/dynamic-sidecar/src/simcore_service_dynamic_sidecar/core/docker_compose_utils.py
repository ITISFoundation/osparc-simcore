import logging
from typing import Optional

from ..models.shared_store import SharedStore
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


async def _cleanup_containers_and_volumes(
    compose_spec: str, settings: DynamicSidecarSettings
) -> None:
    command = (
        'docker-compose --project-name {project} --file "{file_path}" rm --force -v'
    )
    result = await _write_file_and_run_command(
        settings=settings,
        file_content=compose_spec,
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


async def docker_compose_up(
    shared_store: SharedStore, settings: DynamicSidecarSettings, command_timeout: float
) -> CommandResult:

    if not shared_store.compose_spec:
        return CommandResult(True, "No started spec to remove was found")

    await _cleanup_containers_and_volumes(shared_store.compose_spec, settings)

    command = 'docker-compose --project-name {project} --file "{file_path}" up --no-build --detach'

    result = await _write_file_and_run_command(
        settings=settings,
        file_content=shared_store.compose_spec,
        command=command,
        command_timeout=command_timeout,
    )

    return result


async def docker_compose_down(
    shared_store: SharedStore, settings: DynamicSidecarSettings, command_timeout: float
) -> CommandResult:

    if not shared_store.compose_spec:
        return CommandResult(True, "No started spec to remove was found")

    await _cleanup_containers_and_volumes(shared_store.compose_spec, settings)

    command = (
        'docker-compose --project-name {project} --file "{file_path}" '
        "down --volumes --remove-orphans --timeout {stop_and_remove_timeout}"
    )
    result = await _write_file_and_run_command(
        settings=settings,
        file_content=shared_store.compose_spec,
        command=command,
        command_timeout=command_timeout,
    )

    # removing compose-file spec
    shared_store.compose_spec = None
    shared_store.container_names = []

    return result


async def docker_compose_config(
    compose_spec: str, settings: DynamicSidecarSettings, command_timeout: float
) -> CommandResult:
    command = 'docker-compose --file "{file_path}" config'
    result = await _write_file_and_run_command(
        settings=settings,
        file_content=compose_spec,
        command=command,
        command_timeout=command_timeout,
    )
    return result


async def docker_compose_restart(
    compose_spec: str, settings: DynamicSidecarSettings, command_timeout: float
) -> CommandResult:
    command = (
        'docker-compose --project-name {project} --file "{file_path}" '
        "restart --timeout {stop_and_remove_timeout}"
    )
    result = await _write_file_and_run_command(
        settings=settings,
        file_content=compose_spec,
        command=command,
        command_timeout=command_timeout,
    )
    return result
