from typing import Any

from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import ContainersComposeSpec
from models_library.api_schemas_dynamic_sidecar.containers import (
    ActivityInfoOrNone,
)
from servicelib.rabbitmq import RPCRouter

from ...core.validation import InvalidComposeSpecError
from ...services import containers

router = RPCRouter()


@router.expose(reraise_if_error_type=(InvalidComposeSpecError,))
async def create_compose_spec(
    app: FastAPI,
    *,
    containers_compose_spec: ContainersComposeSpec,
) -> None:
    """
    Validates and stores the docker compose spec for the user services.
    """
    await containers.create_compose_spec(app, containers_compose_spec=containers_compose_spec)


@router.expose()
async def containers_docker_inspect(app: FastAPI, *, only_status: bool) -> dict[str, Any]:
    """
    Returns entire docker inspect data, if only_state is True,
    the status of the containers is returned
    """
    return await containers.containers_docker_inspect(app, only_status=only_status)


@router.expose()
async def get_containers_activity(app: FastAPI) -> ActivityInfoOrNone:
    """
    If user service declared an inactivity hook, this endpoint provides
    information about how much time has passed since the service became inactive.
    """
    return await containers.get_containers_activity(app=app)


@router.expose()
async def get_containers_name(app: FastAPI, *, filters: str) -> str | dict[str, Any]:
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
    return await containers.get_containers_name(app=app, filters=filters)


@router.expose()
async def inspect_container(app: FastAPI, *, container_id: str) -> dict[str, Any]:
    """Returns information about the container, like docker inspect command"""
    return await containers.inspect_container(app=app, container_id=container_id)
