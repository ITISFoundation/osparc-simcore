import logging
from typing import Tuple

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse
from ..storage import AsyncStore
from ..settings import ServiceSidecarSettings
from ..utils import (
    InvalidComposeSpec,
    validate_compose_spec,
    write_to_tmp_file,
    async_command,
)

compose_router = APIRouter()

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
        logger.debug("Will run command '%s' and file:\n%s", command, formatted_command)
        return await async_command(formatted_command)


async def remove_the_compose_spec(
    async_store: AsyncStore, settings: ServiceSidecarSettings
):

    stored_compose_content = await async_store.get()
    if stored_compose_content is None:
        return True, "No started spec to remove was found"

    command = (
        "docker-compose -p {project} -f {file_path} "
        "down --remove-orphans -t {stop_and_remove_timeout}"
    )
    result = await write_file_and_run_command(
        settings=settings, file_content=stored_compose_content, command=command
    )
    await async_store.update(None)  # removing compose-file spec
    return result


@compose_router.post("/compose:preload", response_class=PlainTextResponse)
async def create_docker_compose_configuration_containers_without_starting(
    request: Request, response: Response
) -> str:
    """ Expects the docker-compose spec as raw-body utf-8 encoded text """
    body_as_text = (await request.body()).decode("utf-8")

    settings: ServiceSidecarSettings = request.app.state.settings

    try:
        validate_compose_spec(settings, body_as_text)
    except InvalidComposeSpec as e:
        response.status_code = 400
        return str(e)

    async_store: AsyncStore = request.app.state.async_store

    await async_store.update(body_as_text)

    # --no-build might be a security risk building is disabled
    command = "docker-compose -p {project} -f {file_path} up --no-build --no-start"

    finished_without_errors, stdout = await write_file_and_run_command(
        settings=settings, file_content=await async_store.get(), command=command
    )
    response.status_code = 200 if finished_without_errors else 400
    return stdout


@compose_router.put("/compose:stop", response_class=PlainTextResponse)
async def stop_containers_without_removing_them(
    request: Request, response: Response
) -> str:
    """Stops the previously started service
    and returns the docker-compose output"""
    async_store: AsyncStore = request.app.state.async_store
    settings: ServiceSidecarSettings = request.app.state.settings

    stored_compose_content = await async_store.get()
    if stored_compose_content is None:
        response.status_code = 400
        return "No started spec to stop was found"

    command = (
        "docker-compose -p {project} -f {file_path} stop -t {stop_and_remove_timeout}"
    )
    finished_without_errors, stdout = await write_file_and_run_command(
        settings=settings, file_content=stored_compose_content, command=command
    )

    response.status_code = 200 if finished_without_errors else 400
    return stdout


@compose_router.post("/compose", response_class=PlainTextResponse)
async def start_or_update_docker_compose_configuration(
    request: Request, response: Response
) -> str:
    """ Expects the docker-compose spec as raw-body utf-8 encoded text """
    body_as_text = (await request.body()).decode("utf-8")

    settings: ServiceSidecarSettings = request.app.state.settings

    try:
        validate_compose_spec(settings, body_as_text)
    except InvalidComposeSpec as e:
        response.status_code = 400
        return str(e)

    async_store: AsyncStore = request.app.state.async_store
    settings: ServiceSidecarSettings = request.app.state.settings

    await async_store.update(body_as_text)

    # --no-build might be a security risk building is disabled
    command = "docker-compose -p {project} -f {file_path} up --no-build -d"

    finished_without_errors, stdout = await write_file_and_run_command(
        settings=settings, file_content=await async_store.get(), command=command
    )
    response.status_code = 200 if finished_without_errors else 400
    return stdout


@compose_router.delete("/compose", response_class=PlainTextResponse)
async def remove_docker_compose_configuration(
    request: Request, response: Response
) -> str:
    """Removes the previously started service
    and returns the docker-compose output"""
    finished_without_errors, stdout = await remove_the_compose_spec(
        async_store=request.app.state.async_store, settings=request.app.settings
    )
    response.status_code = 200 if finished_without_errors else 400
    return stdout


__all__ = ["compose_router"]