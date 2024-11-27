# pylint: disable=too-many-arguments

import json
import logging
from asyncio import Lock
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path as PathParam
from fastapi import Query, Request, status
from models_library.api_schemas_dynamic_sidecar.containers import (
    ActivityInfo,
    ActivityInfoOrNone,
)
from pydantic import TypeAdapter, ValidationError
from servicelib.fastapi.requests_decorators import cancel_on_disconnect

from ...core.docker_utils import docker_client
from ...core.errors import (
    ContainerExecCommandFailedError,
    ContainerExecContainerNotFoundError,
    ContainerExecTimeoutError,
)
from ...core.settings import ApplicationSettings
from ...core.validation import (
    ComposeSpecValidation,
    parse_compose_spec,
    validate_compose_spec,
)
from ...models.schemas.containers import ContainersComposeSpec
from ...models.shared_store import SharedStore
from ...modules.container_utils import run_command_in_container
from ...modules.mounted_fs import MountedVolumes
from ._dependencies import (
    get_container_restart_lock,
    get_mounted_volumes,
    get_settings,
    get_shared_store,
)

_INACTIVE_FOR_LONG_TIME: Final[int] = 2**63 - 1

_logger = logging.getLogger(__name__)


def _raise_if_container_is_missing(
    container_id: str, container_names: list[str]
) -> None:
    if container_id not in container_names:
        message = f"No container '{container_id}' was started. Started containers '{container_names}'"
        _logger.warning(message)
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


router = APIRouter()


@router.post(
    "/containers/compose-spec",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"}
    },
)
@cancel_on_disconnect
async def store_compose_spec(
    request: Request,
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    containers_compose_spec: ContainersComposeSpec,
    shared_store: Annotated[SharedStore, Depends(get_shared_store)],
    mounted_volumes: Annotated[MountedVolumes, Depends(get_mounted_volumes)],
):
    """
    Validates and stores the docker compose spec for the user services.
    """
    _ = request

    async with shared_store:
        compose_spec_validation: ComposeSpecValidation = await validate_compose_spec(
            settings=settings,
            compose_file_content=containers_compose_spec.docker_compose_yaml,
            mounted_volumes=mounted_volumes,
        )
        shared_store.compose_spec = compose_spec_validation.compose_spec
        shared_store.container_names = compose_spec_validation.current_container_names
        shared_store.original_to_container_names = (
            compose_spec_validation.original_to_current_container_names
        )

    _logger.info("Validated compose-spec:\n%s", f"{shared_store.compose_spec}")

    assert shared_store.compose_spec  # nosec


@router.get(
    "/containers",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"}
    },
)
@cancel_on_disconnect
async def containers_docker_inspect(
    request: Request,
    shared_store: Annotated[SharedStore, Depends(get_shared_store)],
    container_restart_lock: Annotated[Lock, Depends(get_container_restart_lock)],
    only_status: bool = Query(  # noqa: FBT001
        default=False, description="if True only show the status of the container"
    ),
) -> dict[str, Any]:
    """
    Returns entire docker inspect data, if only_state is True,
    the status of the containers is returned
    """
    _ = request

    def _format_result(container_inspect: dict[str, Any]) -> dict[str, Any]:
        if only_status:
            container_state = container_inspect.get("State", {})

            # pending is another fake state use to share more information with the frontend
            return {
                "Status": container_state.get("Status", "pending"),
                "Error": container_state.get("Error", ""),
            }

        return container_inspect

    async with container_restart_lock, docker_client() as docker:
        container_names = shared_store.container_names

        results = {}

        for container in container_names:
            container_instance = await docker.containers.get(container)
            container_inspect = await container_instance.show()
            results[container] = _format_result(container_inspect)

        return results


@router.get(
    "/containers/activity",
)
@cancel_on_disconnect
async def get_containers_activity(
    request: Request,
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    shared_store: Annotated[SharedStore, Depends(get_shared_store)],
) -> ActivityInfoOrNone:
    _ = request
    inactivity_command = settings.DY_SIDECAR_CALLBACKS_MAPPING.inactivity
    if inactivity_command is None:
        return None

    container_name = inactivity_command.service

    try:
        inactivity_response = await run_command_in_container(
            shared_store.original_to_container_names[inactivity_command.service],
            command=inactivity_command.command,
            timeout=inactivity_command.timeout,
        )
    except (
        ContainerExecContainerNotFoundError,
        ContainerExecCommandFailedError,
        ContainerExecTimeoutError,
    ):
        _logger.warning(
            "Could not run inactivity command '%s' in container '%s'",
            inactivity_command.command,
            container_name,
            exc_info=True,
        )
        return ActivityInfo(seconds_inactive=_INACTIVE_FOR_LONG_TIME)

    try:
        return TypeAdapter(ActivityInfo).validate_json(inactivity_response)
    except ValidationError:
        _logger.warning(
            "Could not parse command result '%s' as '%s'",
            inactivity_response,
            ActivityInfo.__name__,
            exc_info=True,
        )

    return ActivityInfo(seconds_inactive=_INACTIVE_FOR_LONG_TIME)


# Some of the operations and sub-resources on containers are implemented as long-running tasks.
# Handlers for these operations can be found in:
#
# POST /containers                       : SEE containers_long_running_tasks::create_service_containers_task
# POST /containers:down                  : SEE containers_long_running_tasks::runs_docker_compose_down_task
# POST /containers/state:restore         : SEE containers_long_running_tasks::state_restore_task
# POST /containers/state:save            : SEE containers_long_running_tasks::state_save_task
# POST /containers/ports/inputs:pull     : SEE containers_long_running_tasks::ports_inputs_pull_task
# POST /containers/ports/outputs:pull    : SEE containers_long_running_tasks::ports_outputs_pull_task
# POST /containers/ports/outputs:push    : SEE containers_long_running_tasks::ports_outputs_push_task
#


@router.get(
    "/containers/{id}/logs",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Container does not exists",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"},
    },
)
@cancel_on_disconnect
async def get_container_logs(
    request: Request,
    shared_store: Annotated[SharedStore, Depends(get_shared_store)],
    container_id: str = PathParam(..., alias="id"),
    since: int = Query(
        default=0,
        title="Timestamp",
        description="Only return logs since this time, as a UNIX timestamp",
    ),
    until: int = Query(
        default=0,
        title="Timestamp",
        description="Only return logs before this time, as a UNIX timestamp",
    ),
    timestamps: bool = Query(  # noqa: FBT001
        default=False,
        title="Display timestamps",
        description="Enabling this parameter will include timestamps in logs",
    ),
) -> list[str]:
    """Returns the logs of a given container if found"""
    _ = request

    _raise_if_container_is_missing(container_id, shared_store.container_names)

    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)

        args = {"stdout": True, "stderr": True, "since": since, "until": until}
        if timestamps:
            args["timestamps"] = True

        container_logs: list[str] = await container_instance.log(
            **args
        )  # type:ignore[call-overload]
        return container_logs


@router.get(
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
@cancel_on_disconnect
async def get_containers_name(
    request: Request,
    shared_store: Annotated[SharedStore, Depends(get_shared_store)],
    filters: str = Query(
        ...,
        description=(
            "JSON encoded dictionary. FastAPI does not "
            "allow for dict as type in query parameters"
        ),
    ),
) -> str | dict[str, Any]:
    """
    Searches for the container's name given the network
    on which the proxy communicates with it.
    Supported filters:
        network: matches against the exact network name
            assigned to the container; `will include`
            containers
        exclude: matches if contained in the name of the
            container; `will exclude` containers
    """
    _ = request

    filters_dict: dict[str, str] = json.loads(filters)
    if not isinstance(filters_dict, dict):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Provided filters, could not parsed {filters_dict}",
        )
    network_name: str | None = filters_dict.get("network", None)
    exclude: str | None = filters_dict.get("exclude", None)

    stored_compose_content = shared_store.compose_spec
    if stored_compose_content is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No spec for docker compose down was found",
        )

    compose_spec = parse_compose_spec(stored_compose_content)

    container_name = None

    spec_services = compose_spec["services"]
    for service in spec_services:
        service_content = spec_services[service]
        if network_name in service_content.get("networks", {}):
            if exclude is not None and exclude in service_content["container_name"]:
                # removing this container from results
                continue
            container_name = service_content["container_name"]
            break

    if container_name is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No container found for network={network_name}",
        )

    return f"{container_name}"


@router.get(
    "/containers/{id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Container does not exist"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"},
    },
)
@cancel_on_disconnect
async def inspect_container(
    request: Request,
    shared_store: Annotated[SharedStore, Depends(get_shared_store)],
    container_id: str = PathParam(..., alias="id"),
) -> dict[str, Any]:
    """Returns information about the container, like docker inspect command"""
    _ = request

    _raise_if_container_is_missing(container_id, shared_store.container_names)

    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)
        inspect_result: dict[str, Any] = await container_instance.show()
        return inspect_result
