# pylint: disable=redefined-builtin
# pylint: disable=too-many-arguments

import functools
import json
import logging
from typing import Any, Union

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
from pydantic import BaseModel
from servicelib.fastapi.requests_decorators import cancel_on_disconnect

from ..core.docker_compose_utils import docker_compose_down, docker_compose_up
from ..core.docker_logs import start_log_fetching, stop_log_fetching
from ..core.docker_utils import docker_client
from ..core.rabbitmq import RabbitMQ
from ..core.settings import DynamicSidecarSettings
from ..core.utils import assemble_container_names
from ..core.validation import (
    InvalidComposeSpec,
    parse_compose_spec,
    validate_compose_spec,
)
from ..models.schemas.application_health import ApplicationHealth
from ..models.shared_store import ContainerNameStr, SharedStore
from ..modules.directory_watcher import directory_watcher_disabled
from ..modules.mounted_fs import MountedVolumes
from ._dependencies import (
    get_application,
    get_application_health,
    get_mounted_volumes,
    get_rabbitmq,
    get_settings,
    get_shared_store,
)

logger = logging.getLogger(__name__)
assert cancel_on_disconnect  # nosec


async def send_message(rabbitmq: RabbitMQ, message: str) -> None:
    logger.info(message)
    await rabbitmq.post_log_message(f"[sidecar] {message}")


async def _task_docker_compose_up_and_send_message(
    settings: DynamicSidecarSettings,
    shared_store: SharedStore,
    app: FastAPI,
    application_health: ApplicationHealth,
    rabbitmq: RabbitMQ,
    command_timeout: float,
) -> None:
    # building is a security risk hence is disabled via "--no-build" parameter
    await send_message(rabbitmq, "starting service containers")
    assert shared_store.compose_spec  # nosec

    with directory_watcher_disabled(app):
        r = await docker_compose_up(
            shared_store, settings, command_timeout=command_timeout
        )

    message = f"Finished docker-compose up with output\n{r.decoded_stdout}"

    if r.success:
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


def _raise_if_container_is_missing(id: str, container_names: list[str]) -> None:
    if id not in container_names:
        message = (
            f"No container '{id}' was started. Started containers '{container_names}'"
        )
        logger.warning(message)
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


#
# API Schema Models ------------------
#


class ContainersCreate(BaseModel):
    docker_compose_yaml: str


#
# HANDLERS ------------------
#
containers_router = APIRouter(tags=["containers"])


@containers_router.post(
    "/containers",
    summary="Run docker-compose up",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=list[ContainerNameStr],
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Cannot validate submitted compose spec"
        }
    },
)
@cancel_on_disconnect
async def create_containers(
    request: Request,
    containers_create: ContainersCreate,
    background_tasks: BackgroundTasks,
    command_timeout: float = Query(
        3600.0, description="docker-compose up command timeout run as a background"
    ),
    validation_timeout: float = Query(
        60.0, description="docker-compose config timeout (EXPERIMENTAL)"
    ),
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
    app: FastAPI = Depends(get_application),
    application_health: ApplicationHealth = Depends(get_application_health),
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
):
    assert request  # nosec

    try:
        shared_store.compose_spec = await validate_compose_spec(
            settings=settings,
            compose_file_content=containers_create.docker_compose_yaml,
            mounted_volumes=mounted_volumes,
            docker_compose_config_timeout=validation_timeout,
        )
        shared_store.container_names = assemble_container_names(
            shared_store.compose_spec
        )

        logger.debug("Validated compose-spec:\n%s", f"{shared_store.compose_spec}")

    except InvalidComposeSpec as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{e}") from e

    # run docker-compose in a background queue and return early
    assert shared_store.compose_spec is not None  # nosec
    background_tasks.add_task(
        functools.partial(
            _task_docker_compose_up_and_send_message,
            settings=settings,
            shared_store=shared_store,
            app=app,
            application_health=application_health,
            rabbitmq=rabbitmq,
            command_timeout=command_timeout,
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
        10.0, description="docker-compose down command timeout default  (EXPERIMENTAL)"
    ),
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
    app: FastAPI = Depends(get_application),
) -> Union[str, dict[str, Any]]:
    """Removes the previously started service
    and returns the docker-compose output"""

    if shared_store.compose_spec is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No compose-specs were found",
        )

    result = await docker_compose_down(
        shared_store=shared_store,
        settings=settings,
        command_timeout=command_timeout,
    )

    for container_name in shared_store.container_names:
        await stop_log_fetching(app, container_name)

    if not result.success:
        logger.warning(
            "docker-compose down command finished with errors\n%s",
            result.decoded_stdout,
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.decoded_stdout
        )

    return result.decoded_stdout


@containers_router.get(
    "/containers",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"}
    },
)
# FIXME: @cancel_on_disconnect
async def containers_docker_inspect(
    request: Request,
    only_status: bool = Query(
        False, description="if True only show the status of the container"
    ),
    shared_store: SharedStore = Depends(get_shared_store),
) -> dict[str, Any]:
    """
    Returns entire docker inspect data, if only_state is True,
    the status of the containers is returned
    """
    assert request  # nosec

    def _format_result(container_inspect: dict[str, Any]) -> dict[str, Any]:
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
# FIXME: @cancel_on_disconnect
async def get_container_logs(
    request: Request,
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
) -> list[str]:
    """Returns the logs of a given container if found"""
    assert request  # nosec

    _raise_if_container_is_missing(id, shared_store.container_names)

    async with docker_client() as docker:
        container_instance = await docker.containers.get(id)

        args = dict(stdout=True, stderr=True, since=since, until=until)
        if timestamps:
            args["timestamps"] = True

        container_logs: list[str] = await container_instance.log(**args)
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
# FIXME: @cancel_on_disconnect
async def get_containers_name(
    request: Request,
    filters: str = Query(
        ...,
        description=(
            "JSON encoded dictionary. FastAPI does not "
            "allow for dict as type in query parameters"
        ),
    ),
    shared_store: SharedStore = Depends(get_shared_store),
) -> Union[str, dict[str, Any]]:
    """
    Searches for the container's name given the network
    on which the proxy communicates with it.
    Supported filters:
        network: name of the network
    """
    assert request  # nosec

    filters_dict: dict[str, str] = json.loads(filters)
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
# FIXME: @cancel_on_disconnect
async def inspect_container(
    request: Request, id: str, shared_store: SharedStore = Depends(get_shared_store)
) -> dict[str, Any]:
    """Returns information about the container, like docker inspect command"""
    _raise_if_container_is_missing(id, shared_store.container_names)
    assert request  # nosec

    async with docker_client() as docker:
        container_instance = await docker.containers.get(id)
        inspect_result: dict[str, Any] = await container_instance.show()
        return inspect_result
