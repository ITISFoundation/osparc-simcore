from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    RPCDynamicServiceCreate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from servicelib.rabbitmq import RPCRouter

from ...services.director_v2 import DirectorV2Client

router = RPCRouter()


@router.expose()
async def get_service_status(
    app: FastAPI, node_id: NodeID
) -> NodeGet | DynamicServiceGet | NodeGetIdle:
    director_v2_client = DirectorV2Client.get_from_app_state(app)
    return await director_v2_client.get_status(node_id)


@router.expose()
async def run_dynamic_service(
    app: FastAPI, rpc_dynamic_service_create: RPCDynamicServiceCreate
) -> NodeGet | DynamicServiceGet:
    director_v2_client = DirectorV2Client.get_from_app_state(app)
    return await director_v2_client.run_dynamic_service(rpc_dynamic_service_create)
