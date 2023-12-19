import logging

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
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def get_service_status(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, node_id: NodeID
) -> NodeGetIdle | DynamicServiceGet | NodeGet:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "get_service_status"),
        node_id=node_id,
    )
    assert isinstance(result, NodeGetIdle | DynamicServiceGet | NodeGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def run_dynamic_service(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_dynamic_service_create: RPCDynamicServiceCreate,
) -> DynamicServiceGet | NodeGet:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "run_dynamic_service"),
        rpc_dynamic_service_create=rpc_dynamic_service_create,
    )
    assert isinstance(result, DynamicServiceGet | NodeGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def stop_dynamic_service(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    simcore_user_agent: str,
    save_state: bool,
) -> None:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "stop_dynamic_service"),
        node_id=node_id,
        simcore_user_agent=simcore_user_agent,
        save_state=save_state,
    )
    assert result is None  # nosec
