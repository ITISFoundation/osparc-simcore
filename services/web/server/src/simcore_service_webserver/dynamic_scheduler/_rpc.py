import logging

from aiohttp import web
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler import DYNAMIC_SCHEDULER_RPC_NAMESPACE
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    RPCDynamicServiceCreate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import parse_obj_as
from servicelib.logging_utils import log_decorator

from ..rabbitmq import get_rabbitmq_rpc_client

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def get_service_status(
    app: web.Application, *, node_id: NodeID
) -> NodeGetIdle | DynamicServiceGet | NodeGet:
    rpc_client = get_rabbitmq_rpc_client(app)

    result = await rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "get_service_status"),
        node_id=node_id,
    )
    assert isinstance(result, NodeGetIdle | DynamicServiceGet | NodeGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def run_dynamic_service(
    app: web.Application, *, rpc_dynamic_service_create: RPCDynamicServiceCreate
) -> DynamicServiceGet | NodeGet:
    rpc_client = get_rabbitmq_rpc_client(app)

    result = await rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "run_dynamic_service"),
        create_dynamic_service=rpc_dynamic_service_create,
    )
    assert isinstance(result, DynamicServiceGet | NodeGet)  # nosec
    return result
