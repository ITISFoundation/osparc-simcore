import logging
import traceback
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import PlainTextResponse
from starlette.status import HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST

from ..dependencies import get_settings, get_shared_store
from ..settings import DynamicSidecarSettings
from ..shared_handlers import remove_the_compose_spec, write_file_and_run_command
from ..shared_store import SharedStore
from ..utils import assemble_container_names
from ..validation import InvalidComposeSpec, validate_compose_spec

logger = logging.getLogger(__name__)
compose_router = APIRouter(tags=["docker-compose"])


@compose_router.post(
    "/compose:store", response_class=PlainTextResponse, responses={204: {"model": None}}
)
async def validates_docker_compose_spec_and_stores_it(
    request: Request,
    response: Response,
    command_timeout: float = 5.0,
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
) -> Optional[str]:
    # FIXME: why is this not an argument into CREATE /containers ?

    """ Expects the docker-compose spec as raw-body utf-8 encoded text """
    body_as_text = (await request.body()).decode("utf-8")

    if body_as_text is None:
        shared_store.compose_spec = None
        shared_store.container_names = []
        return None

    try:
        shared_store.compose_spec = await validate_compose_spec(
            settings=settings,
            compose_file_content=body_as_text,
            command_timeout=command_timeout,
        )
        shared_store.container_names = assemble_container_names(
            shared_store.compose_spec
        )
    except InvalidComposeSpec as e:
        logger.warning("Error detected %s", traceback.format_exc())
        response.status_code = HTTP_400_BAD_REQUEST
        return str(e)

    response.status_code = HTTP_204_NO_CONTENT
    return None


@compose_router.post("/compose", response_class=PlainTextResponse)
async def runs_docker_compose_up(
    response: Response,
    command_timeout: float,
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
) -> str:
    """ Expects the docker-compose spec as raw-body utf-8 encoded text """
    # FIXME: why is this not in /containers:up ?

    # --no-build might be a security risk building is disabled
    command = (
        "docker-compose --project-name {project} --file {file_path} "
        "up --no-build --detach"
    )
    finished_without_errors, stdout = await write_file_and_run_command(
        settings=settings,
        file_content=shared_store.compose_spec,
        command=command,
        command_timeout=command_timeout,
    )

    response.status_code = (
        HTTP_200_OK if finished_without_errors else HTTP_400_BAD_REQUEST
    )
    return stdout


@compose_router.get("/compose:pull", response_class=PlainTextResponse)
async def runs_docker_compose_pull(
    response: Response,
    command_timeout: float,
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
) -> str:
    """ Expects the docker-compose spec as raw-body utf-8 encoded text """
    # FIXME: why is this not in /containers:pull ?
    stored_compose_content = shared_store.compose_spec
    if stored_compose_content is None:
        response.status_code = HTTP_400_BAD_REQUEST
        return "No started spec to pull was found"

    command = (
        "docker-compose --project-name {project} --file {file_path} "
        "pull --include-deps"
    )

    try:
        # mark as pulling images
        shared_store.is_pulling_containers = True

        finished_without_errors, stdout = await write_file_and_run_command(
            settings=settings,
            file_content=stored_compose_content,
            command=command,
            command_timeout=command_timeout,
        )
    finally:
        # remove mark
        shared_store.is_pulling_containers = False

    response.status_code = (
        HTTP_200_OK if finished_without_errors else HTTP_400_BAD_REQUEST
    )
    return stdout


@compose_router.delete("/compose", response_class=PlainTextResponse)
async def runs_docker_compose_down(
    response: Response,
    command_timeout: float,
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
) -> str:
    # FIXME: why is this not in /containers:down ?

    """Removes the previously started service
    and returns the docker-compose output"""
    finished_without_errors, stdout = await remove_the_compose_spec(
        shared_store=shared_store,
        settings=settings,
        command_timeout=command_timeout,
    )

    response.status_code = (
        HTTP_200_OK if finished_without_errors else HTTP_400_BAD_REQUEST
    )
    return stdout


__all__ = ["compose_router"]
