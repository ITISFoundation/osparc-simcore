import logging

from typing import Tuple

from fastapi import FastAPI

from .storage import AsyncStore
from .settings import ServiceSidecarSettings
from .utils import write_to_tmp_file, async_command

logger = logging.getLogger(__name__)


async def write_file_and_run_command(
    settings: ServiceSidecarSettings, file_content: str, command: str
) -> Tuple[bool, str]:
    """ The command which accepts {file_path} as an argument for string formatting """

    # pylint: disable=not-async-context-manager
    async with write_to_tmp_file(file_content) as file_path:
        formatted_command = command.format(
            file_path=file_path,
            project=settings.compose_namespace,
            stop_and_remove_timeout=settings.stop_and_remove_timeout,
        )
        logger.debug("Will run command\n'%s':\n%s", formatted_command, file_content)
        return await async_command(formatted_command)


async def remove_the_compose_spec(
    async_store: AsyncStore, settings: ServiceSidecarSettings
) -> None:

    stored_compose_content = async_store.get_spec()
    if stored_compose_content is None:
        return True, "No started spec to remove was found"

    command = (
        "docker-compose -p {project} -f {file_path} "
        "down --remove-orphans -t {stop_and_remove_timeout}"
    )
    result = await write_file_and_run_command(
        settings=settings, file_content=stored_compose_content, command=command
    )
    async_store.put_spec(None)  # removing compose-file spec
    return result


async def on_shutdown_handler(app: FastAPI) -> None:
    logging.info("Going to remove spawned containers")
    async_store: AsyncStore = app.state.async_store
    settings: ServiceSidecarSettings = app.state.settings

    result = await remove_the_compose_spec(async_store=async_store, settings=settings)
    logging.info("Container removal did_succeed=%s\n%s", result[0], result[1])
