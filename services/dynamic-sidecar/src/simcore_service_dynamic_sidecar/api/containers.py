import logging
import traceback

# pylint: disable=redefined-builtin
from typing import Any, Dict, Optional, Union

import aiodocker
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
from ..utils import assemble_container_names, docker_client
from ..validation import InvalidComposeSpec, validate_compose_spec

logger = logging.getLogger(__name__)

containers_router = APIRouter(tags=["containers"])


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


@containers_router.post("/containers", status_code=status.HTTP_201_CREATED)
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


@containers_router.post("/containers:down", response_class=PlainTextResponse)
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


@containers_router.get(
    "/containers:inspect",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Erros in container"}
    },
)
async def containers_inspect(
    shared_store: SharedStore = Depends(get_shared_store),
) -> Dict[str, Any]:
    """ Returns information about the container, like docker inspect command """
    with docker_client() as docker:
        results = {}

        for container in shared_store.container_names:
            try:
                container_instance = await docker.containers.get(container)
                results[container] = await container_instance.show()
            except aiodocker.exceptions.DockerError as err:
                logger.warning(
                    "An unexpected Docker error occurred:\n%s",
                    str(traceback.format_exc()),
                )
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err.message
                ) from err

        return results


@containers_router.get(
    "/containers",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"}
    },
)
async def containers_docker_status(
    shared_store: SharedStore = Depends(get_shared_store),
) -> Dict[str, Any]:
    """ Returns the status of the containers """

    with docker_client() as docker:
        container_names = shared_store.container_names

        # if containers are being pulled, return pulling (fake status)
        if shared_store.is_pulling_containers:
            # pulling is a fake state use to share more information with the frontend
            return {x: {"Status": "pulling", "Error": ""} for x in container_names}

        results = {}

        for container in container_names:
            try:
                container_instance = await docker.containers.get(container)
                container_inspect = await container_instance.show()
                container_state = container_inspect.get("State", {})

                # pending is another fake state use to share more information with the frontend
                results[container] = {
                    "Status": container_state.get("Status", "pending"),
                    "Error": container_state.get("Error", ""),
                }
            except aiodocker.exceptions.DockerError as err:
                logger.warning(
                    "An unexpected Docker error occurred:\n%s",
                    str(traceback.format_exc()),
                )
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err.message
                ) from err

        return results


@containers_router.get(
    "/containers/{id}:logs",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Container does not exists"
        }
    },
)
async def get_container_logs(
    id: str,
    since: int = Query(
        0,
        title="Timestamp",
        description="Only return logs since this time, as a UNIX timestamp",
    ),
    until: int = Query(
        0,
        title="Timestamp",
        description="Only return logs before this time, as a UNIX timestamp",
    ),
    timestamps: bool = Query(
        False,
        title="Display timestamps",
        description="Enabling this parameter will include timestamps in logs",
    ),
    shared_store: SharedStore = Depends(get_shared_store),
) -> Union[str, Dict[str, Any]]:
    """ Returns the logs of a given container if found """
    # TODO: remove from here and dump directly into the logs of this service
    # do this in PR#1887
    if id not in shared_store.container_names:
        message = f"No container '{id}' was started. Started containers '{shared_store.container_names}'"
        logger.warning(message)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    with docker_client() as docker:
        try:
            container_instance = await docker.containers.get(id)

            args = dict(stdout=True, stderr=True)
            if timestamps:
                args["timestamps"] = True

            if since or until:
                raise HTTPException(
                    status.HTTP_501_NOT_IMPLEMENTED,
                    detail="since and until options are still not implemented",
                )

            container_logs: str = await container_instance.log(**args)
            return container_logs
        except aiodocker.exceptions.DockerError as err:
            logger.warning(
                "An unexpected Docker error occurred:\n%s", str(traceback.format_exc())
            )
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err.message
            ) from err


@containers_router.get(
    "/containers/{id}:inspect",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Container does not exist"
        }
    },
)
async def inspect_container(
    id: str, shared_store: SharedStore = Depends(get_shared_store)
) -> Dict[str, Any]:
    """ Returns information about the container, like docker inspect command """

    if id not in shared_store.container_names:
        message = f"No container '{id}' was started. Started containers '{shared_store.container_names}'"
        logger.warning(message)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    with docker_client() as docker:
        try:
            container_instance = await docker.containers.get(id)
            inspect_result: Dict[str, Any] = await container_instance.show()
            return inspect_result
        except aiodocker.exceptions.DockerError as err:
            logger.warning(
                "An unexpected Docker error occurred:\n%s", str(traceback.format_exc())
            )
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err.message
            ) from err


@containers_router.delete(
    "/containers/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Container does not exist"
        }
    },
)
async def remove_container(
    id: str, shared_store: SharedStore = Depends(get_shared_store)
) -> Optional[Dict[str, Any]]:
    if id not in shared_store.container_names:
        message = f"No container '{id}' was started. Started containers '{shared_store.container_names}'"
        logger.warning(message)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    with docker_client() as docker:
        try:
            container_instance = await docker.containers.get(id)
            await container_instance.delete()
            return None
        except aiodocker.exceptions.DockerError as err:
            logger.warning(
                "An unexpected Docker error occurred:\n%s", str(traceback.format_exc())
            )
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err.message
            ) from err


__all__ = ["containers_router"]
