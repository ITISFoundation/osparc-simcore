import logging
from typing import Final

from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler import DYNAMIC_SCHEDULER_RPC_NAMESPACE
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    RPCDynamicServiceCreate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import GroupID
from pydantic import NonNegativeInt, parse_obj_as
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)

# the webserver's director-v2 plugin internally uses a
# 20 second default timeout for all HTTP calls
DEFAULT_LEGACY_WB_TO_DV2_HTTP_REQUESTS_TIMEOUT_S: Final[NonNegativeInt] = 20

# make sure RPC calls time out after the HTTP requests
# from dynamic-scheduler to director-v2 time out
_RPC_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = int(
    DEFAULT_LEGACY_WB_TO_DV2_HTTP_REQUESTS_TIMEOUT_S * 2
)


@log_decorator(_logger, level=logging.DEBUG)
async def get_service_status(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, node_id: NodeID
) -> NodeGetIdle | DynamicServiceGet | NodeGet:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "get_service_status"),
        node_id=node_id,
        timeout_s=_RPC_DEFAULT_TIMEOUT_S,
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
        timeout_s=_RPC_DEFAULT_TIMEOUT_S,
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
    primary_group_id: GroupID,
    timeout_s: NonNegativeInt,
) -> None:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "stop_dynamic_service"),
        node_id=node_id,
        simcore_user_agent=simcore_user_agent,
        save_state=save_state,
        primary_group_id=primary_group_id,
        timeout_s=timeout_s,
    )
    assert result is None  # nosec
