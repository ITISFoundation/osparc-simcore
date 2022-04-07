# pylint: disable=redefined-builtin

import functools
import json
import logging
import traceback
from typing import Any, Dict, List, Union

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import PlainTextResponse

from ..core.dependencies import (
    get_application,
    get_application_health,
    get_mounted_volumes,
    get_rabbitmq,
    get_settings,
    get_shared_store,
)
from ..core.docker_logs import start_log_fetching, stop_log_fetching
from ..core.docker_utils import docker_client
from ..core.rabbitmq import RabbitMQ
from ..core.settings import DynamicSidecarSettings
from ..core.shared_handlers import remove_the_compose_spec, write_file_and_run_command
from ..core.utils import assemble_container_names
from ..core.validation import (
    InvalidComposeSpec,
    parse_compose_spec,
    validate_compose_spec,
)
from ..models.domains.shared_store import SharedStore
from ..models.schemas.application_health import ApplicationHealth
from ..modules.mounted_fs import MountedVolumes

logger = logging.getLogger(__name__)

containers_router = APIRouter(tags=["containers"])


async def send_message(rabbitmq: RabbitMQ, message: str) -> None:
    logger.info(message)
    await rabbitmq.post_log_message(f"[sidecar] {message}")


async def _task_docker_compose_up(
    settings: DynamicSidecarSettings,
    shared_store: SharedStore,
    app: FastAPI,
    application_health: ApplicationHealth,
    rabbitmq: RabbitMQ,
) -> None:
    # building is a security risk hence is disabled via "--no-build" parameter
    await send_message(rabbitmq, "starting service containers")
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
        await send_message(rabbitmq, "service containers started")
        logger.info(message)
        for container_name in shared_store.container_names:
            await start_log_fetching(app, container_name)
    else:
        application_health.is_healthy = False
        application_health.error_message = message
        logger.error("Marked sidecar as unhealthy, see below for details\n:%s", message)
        await send_message(rabbitmq, "could not start service containers")

    return None


def _raise_if_container_is_missing(id: str, container_names: List[str]) -> None:
    if id not in container_names:
        message = (
            f"No container '{id}' was started. Started containers '{container_names}'"
        )
        logger.warning(message)
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


@containers_router.post(
    "/containers",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Cannot validate submitted compose spec"
        }
    },
)
async def runs_docker_compose_up(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
    app: FastAPI = Depends(get_application),
    application_health: ApplicationHealth = Depends(get_application_health),
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> Union[List[str], Dict[str, Any]]:
    """Expects the docker-compose spec as raw-body utf-8 encoded text"""

    # stores the compose spec after validation
    body_as_text = (await request.body()).decode("utf-8")

    try:
        shared_store.compose_spec = await validate_compose_spec(
            settings=settings,
            compose_file_content=body_as_text,
            mounted_volumes=mounted_volumes,
        )
        shared_store.container_names = assemble_container_names(
            shared_store.compose_spec
        )
    except InvalidComposeSpec as e:
        logger.warning("Error detected %s", traceback.format_exc())
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

    # run docker-compose in a background queue and return early
    background_tasks.add_task(
        functools.partial(
            _task_docker_compose_up,
            settings=settings,
            shared_store=shared_store,
            app=app,
            application_health=application_health,
            rabbitmq=rabbitmq,
        )
    )

    return shared_store.container_names


@containers_router.post(
    "/containers:down",
    response_class=PlainTextResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "No compose spec found"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error while shutting down containers"
        },
    },
)
async def runs_docker_compose_down(
    command_timeout: float = Query(
        10.0, description="docker-compose down command timeout default"
    ),
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
    app: FastAPI = Depends(get_application),
) -> Union[str, Dict[str, Any]]:
    """Removes the previously started service
    and returns the docker-compose output"""

    stored_compose_content = shared_store.compose_spec
    if stored_compose_content is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No spec for docker-compose down was found",
        )

    finished_without_errors, stdout = await remove_the_compose_spec(
        shared_store=shared_store,
        settings=settings,
        command_timeout=command_timeout,
    )

    for container_name in shared_store.container_names:
        await stop_log_fetching(app, container_name)

    if not finished_without_errors:
        logger.warning("docker-compose down command finished with errors\n%s", stdout)
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
) -> List[str]:
    """Returns the logs of a given container if found"""
    _raise_if_container_is_missing(id, shared_store.container_names)

    async with docker_client() as docker:
        container_instance = await docker.containers.get(id)

        args = dict(stdout=True, stderr=True, since=since, until=until)
        if timestamps:
            args["timestamps"] = True

        container_logs: List[str] = await container_instance.log(**args)
        return container_logs


@containers_router.get(
    "/containers/name",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "No entrypoint container found or spec is not yet present"
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Filters could not be parsed"
        },
    },
)
async def get_entrypoint_container_name(
    filters: str = Query(
        ...,
        description=(
            "JSON encoded dictionary. FastAPI does not "
            "allow for dict as type in query parameters"
        ),
    ),
    shared_store: SharedStore = Depends(get_shared_store),
) -> Union[str, Dict[str, Any]]:
    """
    Searches for the container's name given the network
    on which the proxy communicates with it.
    Supported filters:
        network: name of the network
    """
    filters_dict: Dict[str, str] = json.loads(filters)
    if not isinstance(filters_dict, dict):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Provided filters, could not parsed {filters_dict}",
        )
    network_name = filters_dict.get("network", None)

    stored_compose_content = shared_store.compose_spec
    if stored_compose_content is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No spec for docker-compose down was found",
        )

    compose_spec = parse_compose_spec(stored_compose_content)

    container_name = None

    spec_services = compose_spec["services"]
    for service in spec_services:
        service_content = spec_services[service]
        if network_name in service_content.get("networks", {}):
            container_name = service_content["container_name"]
            break

    if container_name is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No container found for network={network_name}",
        )

    return f"{container_name}"


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


__all__ = ["containers_router"]
