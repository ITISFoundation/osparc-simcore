# pylint: disable=too-many-arguments

import json
import logging
from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path as PathParam
from fastapi import Query, Request, status
from servicelib.fastapi.requests_decorators import cancel_on_disconnect

from ..core.docker_utils import docker_client
from ..core.validation import parse_compose_spec
from ..models.shared_store import SharedStore
from ._dependencies import get_shared_store

logger = logging.getLogger(__name__)


def _raise_if_container_is_missing(
    container_id: str, container_names: list[str]
) -> None:
    if container_id not in container_names:
        message = f"No container '{container_id}' was started. Started containers '{container_names}'"
        logger.warning(message)
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


containers_router = APIRouter(tags=["containers"])


@containers_router.get(
    "/containers",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"}
    },
)
@cancel_on_disconnect
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
@cancel_on_disconnect
async def get_container_logs(
    request: Request,
    container_id: str = PathParam(..., alias="id"),
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

    _raise_if_container_is_missing(container_id, shared_store.container_names)

    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)

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
@cancel_on_disconnect
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
@cancel_on_disconnect
async def inspect_container(
    request: Request,
    container_id: str = PathParam(..., alias="id"),
    shared_store: SharedStore = Depends(get_shared_store),
) -> dict[str, Any]:
    """Returns information about the container, like docker inspect command"""
    assert request  # nosec

    _raise_if_container_is_missing(container_id, shared_store.container_names)

    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)
        inspect_result: dict[str, Any] = await container_instance.show()
        return inspect_result
