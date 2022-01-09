import logging
from typing import Optional, Tuple

from fastapi import FastAPI

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

    stored_compose_content = shared_store.compose_spec
    if stored_compose_content is None:
        return True, "No started spec to remove was found"

    command = (
        "docker-compose -p {project} -f {file_path} "
        "down --volumes --remove-orphans -t {stop_and_remove_timeout}"
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


async def on_shutdown_handler(app: FastAPI) -> None:
    logging.info("Going to remove spawned containers")
    shared_store: SharedStore = app.state.shared_store
    settings: DynamicSidecarSettings = app.state.settings

    result = await remove_the_compose_spec(
        shared_store=shared_store,
        settings=settings,
        command_timeout=settings.DYNAMIC_SIDECAR_DOCKER_COMPOSE_DOWN_TIMEOUT,
    )
    logging.info("Container removal did_succeed=%s\n%s", result[0], result[1])
