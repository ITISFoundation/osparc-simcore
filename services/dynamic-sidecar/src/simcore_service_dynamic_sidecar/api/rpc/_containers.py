from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import ContainersComposeSpec
from servicelib.rabbitmq import RPCRouter

from ...core.validation import InvalidComposeSpecError
from ...services import containers

router = RPCRouter()


@router.expose(reraise_if_error_type=(InvalidComposeSpecError,))
async def store_compose_spec(
    app: FastAPI,
    *,
    containers_compose_spec: ContainersComposeSpec,
) -> None:
    await containers.store_compose_spec(app, containers_compose_spec)
