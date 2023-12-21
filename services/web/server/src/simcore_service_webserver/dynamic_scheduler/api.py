from aiohttp import web
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    RPCDynamicServiceCreate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler import services

from ..rabbitmq import get_rabbitmq_rpc_client


async def get_dynamic_service(
    app: web.Application, *, node_id: NodeID
) -> NodeGetIdle | DynamicServiceGet | NodeGet:
    return await services.get_service_status(
        get_rabbitmq_rpc_client(app), node_id=node_id
    )


async def run_dynamic_service(
    app: web.Application, *, rpc_dynamic_service_create: RPCDynamicServiceCreate
) -> DynamicServiceGet | NodeGet:
    return await services.run_dynamic_service(
        get_rabbitmq_rpc_client(app),
        rpc_dynamic_service_create=rpc_dynamic_service_create,
    )
