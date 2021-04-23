import logging
import traceback
from typing import Any, Dict, Optional, Union

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import PlainTextResponse

from ..dependencies import get_settings, get_shared_store
from ..settings import DynamicSidecarSettings
from ..shared_handlers import remove_the_compose_spec, write_file_and_run_command
from ..shared_store import SharedStore
from ..utils import assemble_container_names
from ..validation import InvalidComposeSpec, validate_compose_spec

logger = logging.getLogger(__name__)
compose_router = APIRouter(tags=["docker-compose"])


async def task_docker_compose_up(
    command_timeout: float,
    settings: DynamicSidecarSettings,
    shared_store: SharedStore,
) -> None:
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
    message = f"Finished {command} with output\n{stdout}"

    if finished_without_errors:
        logger.info(message)
    else:
        logger.error(message)

    return None


@compose_router.post("/containers", status_code=status.HTTP_201_CREATED)
async def runs_docker_compose_up(
    request: Request,
    background_tasks: BackgroundTasks,
    command_timeout: float = Query(
        ...,
        description=(
            "docker-compose up also pulls images, this value "
            "needs to be big enough to account for that"
        ),
    ),
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
) -> Optional[Dict[str, Any]]:
    """ Expects the docker-compose spec as raw-body utf-8 encoded text """

    # stores the compose spec after validation
    body_as_text = (await request.body()).decode("utf-8")

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
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

    # run docker-compose in a background queue and return early
    background_tasks.add_task(
        task_docker_compose_up, command_timeout, settings, shared_store
    )
    return None


@compose_router.post("/containers:down", response_class=PlainTextResponse)
async def runs_docker_compose_down(
    response: Response,
    command_timeout: float,
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
) -> Union[str, Dict[str, Any]]:
    """Removes the previously started service
    and returns the docker-compose output"""

    stored_compose_content = shared_store.compose_spec
    if stored_compose_content is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No spec for docker-compose down was found",
        )

    finished_without_errors, stdout = await remove_the_compose_spec(
        shared_store=shared_store,
        settings=settings,
        command_timeout=command_timeout,
    )

    response.status_code = (
        status.HTTP_200_OK
        if finished_without_errors
        else status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    return stdout


__all__ = ["compose_router"]
