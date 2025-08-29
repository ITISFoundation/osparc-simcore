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
    await containers.create_compose_spec(
        app, containers_compose_spec=containers_compose_spec
    )


@router.expose()
async def containers_docker_inspect(
    app: FastAPI, *, only_status: bool
) -> dict[str, Any]:
    return await containers.containers_docker_inspect(app, only_status=only_status)


@router.expose()
async def get_containers_activity(app: FastAPI) -> ActivityInfoOrNone:
    return await containers.get_containers_activity(app=app)


@router.expose()
async def get_containers_name(app: FastAPI, *, filters: str) -> str | dict[str, Any]:
    return await containers.get_containers_name(app=app, filters=filters)


@router.expose()
async def inspect_container(app: FastAPI, *, container_id: str) -> dict[str, Any]:
    return await containers.inspect_container(app=app, container_id=container_id)
