# pylint: disable=redefined-builtin

import logging
import traceback
from collections import deque
from typing import Any, Awaitable, Deque, Dict, List, Optional, Union

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
from servicelib.utils import logged_gather

from ..core.dependencies import get_application_health, get_settings, get_shared_store
from ..core.settings import DynamicSidecarSettings
from ..core.shared_handlers import remove_the_compose_spec, write_file_and_run_command
from ..core.utils import assemble_container_names, docker_client
from ..core.validation import InvalidComposeSpec, validate_compose_spec
from ..models.domains.shared_store import SharedStore
from ..models.schemas.application_health import ApplicationHealth
from ..modules import nodeports
from ..modules.data_manager import pull_path_if_exists, upload_path_if_exists
from ..modules.mounted_fs import MountedVolumes, get_mounted_volumes

logger = logging.getLogger(__name__)

containers_router = APIRouter(tags=["containers"])


async def task_docker_compose_up(
    settings: DynamicSidecarSettings,
    shared_store: SharedStore,
    application_health: ApplicationHealth = Depends(get_application_health),
) -> None:
    # building is a security risk hence is disabled via "--no-build" parameter
    command = (
        "docker-compose --project-name {project} --file {file_path} "
        "up --no-build --detach"
    )
    finished_without_errors, stdout = await write_file_and_run_command(
        settings=settings,
        file_content=shared_store.compose_spec,
        command=command,
        command_timeout=None,
    )
    message = f"Finished {command} with output\n{stdout}"

    if finished_without_errors:
        logger.info(message)
    else:
        application_health.is_healthy = False
        application_health.error_message = message
        logger.error("Marked sidecar as unhealthy, see below for details\n:%s", message)

    return None


def _raise_if_container_is_missing(id: str, container_names: List[str]) -> None:
    if id not in container_names:
        message = (
            f"No container '{id}' was started. Started containers '{container_names}'"
        )
        logger.warning(message)
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


@containers_router.post("/containers", status_code=status.HTTP_202_ACCEPTED)
async def runs_docker_compose_up(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
) -> Union[List[str], Dict[str, Any]]:
    """Expects the docker-compose spec as raw-body utf-8 encoded text"""

    # stores the compose spec after validation
    body_as_text = (await request.body()).decode("utf-8")

    try:
        shared_store.compose_spec = await validate_compose_spec(
            settings=settings, compose_file_content=body_as_text
        )
        shared_store.container_names = assemble_container_names(
            shared_store.compose_spec
        )
    except InvalidComposeSpec as e:
        logger.warning("Error detected %s", traceback.format_exc())
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

    # run docker-compose in a background queue and return early
    background_tasks.add_task(task_docker_compose_up, settings, shared_store)

    return shared_store.container_names


@containers_router.post("/containers:down", response_class=PlainTextResponse)
async def runs_docker_compose_down(
    command_timeout: float = Query(
        10.0, description="docker-compose down command timeout default"
    ),
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
) -> Union[str, Dict[str, Any]]:
    """Removes the previously started service
    and returns the docker-compose output"""

    stored_compose_content = shared_store.compose_spec
    if stored_compose_content is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No spec for docker-compose down was found",
        )

    finished_without_errors, stdout = await remove_the_compose_spec(
        shared_store=shared_store,
        settings=settings,
        command_timeout=command_timeout,
    )

    if not finished_without_errors:
        logger.warning("docker-compose command finished with errors\n%s", stdout)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=stdout)

    return stdout


@containers_router.get(
    "/containers",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"}
    },
)
async def containers_docker_inspect(
    only_status: bool = Query(
        False, description="if True only show the status of the container"
    ),
    shared_store: SharedStore = Depends(get_shared_store),
) -> Dict[str, Any]:
    """
    Returns entire docker inspect data, if only_state is True,
    the status of the containers is returned
    """

    def _format_result(container_inspect: Dict[str, Any]) -> Dict[str, Any]:
        if only_status:
            container_state = container_inspect.get("State", {})

            # pending is another fake state use to share more information with the frontend
            return {
                "Status": container_state.get("Status", "pending"),
                "Error": container_state.get("Error", ""),
            }

        return container_inspect

    async with docker_client() as docker:
        container_names = shared_store.container_names

        results = {}

        for container in container_names:
            container_instance = await docker.containers.get(container)
            container_inspect = await container_instance.show()
            results[container] = _format_result(container_inspect)

        return results


@containers_router.get(
    "/containers/{id}/logs",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Container does not exists",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"},
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
    """Returns the logs of a given container if found"""
    # TODO: remove from here and dump directly into the logs of this service
    # do this in PR#1887
    _raise_if_container_is_missing(id, shared_store.container_names)

    async with docker_client() as docker:
        container_instance = await docker.containers.get(id)

        args = dict(stdout=True, stderr=True, since=since, until=until)
        if timestamps:
            args["timestamps"] = True

        container_logs: str = await container_instance.log(**args)
        return container_logs


@containers_router.get(
    "/containers/{id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Container does not exist"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"},
    },
)
async def inspect_container(
    id: str, shared_store: SharedStore = Depends(get_shared_store)
) -> Dict[str, Any]:
    """Returns information about the container, like docker inspect command"""
    _raise_if_container_is_missing(id, shared_store.container_names)

    async with docker_client() as docker:
        container_instance = await docker.containers.get(id)
        inspect_result: Dict[str, Any] = await container_instance.show()
        return inspect_result


@containers_router.put(
    "/containers:restore-state",
    summary="Restores the state of the dynamic service",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def restore_state() -> Response:
    """
    When restoring the state:
    - pull inputs via nodeports
    - pull all the extra state paths
    """
    mounted_volumes: MountedVolumes = get_mounted_volumes()

    awaitables: Deque[Awaitable[Optional[Any]]] = deque()

    for state_path in mounted_volumes.disk_state_paths():
        logger.debug("Downloading state %s", state_path)
        awaitables.append(pull_path_if_exists(state_path))

    await logged_gather(*awaitables)

    # SEE https://github.com/tiangolo/fastapi/issues/2253
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@containers_router.put(
    "/containers:save-state",
    summary="Stores the state of the dynamic service",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def save_state() -> Response:
    mounted_volumes: MountedVolumes = get_mounted_volumes()

    awaitables: Deque[Awaitable[Optional[Any]]] = deque()

    for state_path in mounted_volumes.disk_state_paths():
        logger.debug("Saving state %s", state_path)
        awaitables.append(upload_path_if_exists(state_path))

    await logged_gather(*awaitables)

    # SEE https://github.com/tiangolo/fastapi/issues/2253
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@containers_router.put(
    "/containers:pull-nodeports",
    summary="Pull input ports data",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)  # pylint: disable=dangerous-default-value
async def pull_input_ports(port_keys: List[str] = []) -> Response:
    mounted_volumes: MountedVolumes = get_mounted_volumes()

    await nodeports.download_inputs(
        mounted_volumes.disk_inputs_path, port_keys=port_keys
    )

    # SEE https://github.com/tiangolo/fastapi/issues/2253
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@containers_router.put(
    "/containers:push-nodeports",
    summary="Push output ports data",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)  # pylint: disable=dangerous-default-value
async def push_output_ports(port_keys: List[str] = []) -> Response:
    mounted_volumes: MountedVolumes = get_mounted_volumes()

    await nodeports.upload_outputs(
        mounted_volumes.disk_outputs_path, port_keys=port_keys
    )

    # SEE https://github.com/tiangolo/fastapi/issues/2253
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["containers_router"]
