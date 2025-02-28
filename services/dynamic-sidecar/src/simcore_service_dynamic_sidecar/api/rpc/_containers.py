from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.containers import DcokerComposeYamlStr
from pydantic import validate_call
from servicelib.rabbitmq import RPCRouter

from ...services import containers

router = RPCRouter()


@router.expose()
@validate_call(config={"arbitrary_types_allowed": True})
async def store_compose_spec(
    app: FastAPI, *, docker_compose_yaml: DcokerComposeYamlStr
) -> None:
    await containers.store_conpose_spec(app, docker_compose_yaml=docker_compose_yaml)
