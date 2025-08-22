import logging
from typing import Final

from models_library.api_schemas_directorv2.dynamic_services import (
    DynamicServiceGet,
    GetProjectInactivityResponse,
    RetrieveDataOutEnveloped,
)
from models_library.api_schemas_dynamic_scheduler import DYNAMIC_SCHEDULER_RPC_NAMESPACE
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.services_types import ServicePortKey
from models_library.users import UserID
from pydantic import NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ....rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)

# the webserver's director-v2 plugin internally uses a
# 20 second default timeout for all HTTP calls
DEFAULT_LEGACY_WB_TO_DV2_HTTP_REQUESTS_TIMEOUT_S: Final[NonNegativeInt] = 20

# make sure RPC calls time out after the HTTP requests
# from dynamic-scheduler to director-v2 time out
_RPC_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = int(
    DEFAULT_LEGACY_WB_TO_DV2_HTTP_REQUESTS_TIMEOUT_S * 2
)

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
async def list_tracked_dynamic_services(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID | None = None,
    project_id: ProjectID | None = None,
) -> list[DynamicServiceGet]:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("list_tracked_dynamic_services"),
        user_id=user_id,
        project_id=project_id,
        timeout_s=_RPC_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, list)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_service_status(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, node_id: NodeID
) -> NodeGetIdle | DynamicServiceGet | NodeGet:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_service_status"),
        node_id=node_id,
        timeout_s=_RPC_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, NodeGetIdle | DynamicServiceGet | NodeGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def run_dynamic_service(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    dynamic_service_start: DynamicServiceStart,
) -> DynamicServiceGet | NodeGet:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("run_dynamic_service"),
        dynamic_service_start=dynamic_service_start,
        timeout_s=_RPC_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, DynamicServiceGet | NodeGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def stop_dynamic_service(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    dynamic_service_stop: DynamicServiceStop,
    timeout_s: NonNegativeInt,
) -> None:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("stop_dynamic_service"),
        dynamic_service_stop=dynamic_service_stop,
        timeout_s=timeout_s,
    )
    assert result is None  # nosec


@log_decorator(_logger, level=logging.DEBUG)
async def get_project_inactivity(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    project_id: ProjectID,
    max_inactivity_seconds: NonNegativeInt,
) -> GetProjectInactivityResponse:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_project_inactivity"),
        project_id=project_id,
        max_inactivity_seconds=max_inactivity_seconds,
        timeout_s=_RPC_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, GetProjectInactivityResponse)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def restart_user_services(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    timeout_s: NonNegativeInt,
) -> None:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("restart_user_services"),
        node_id=node_id,
        timeout_s=timeout_s,
    )
    assert result is None  # nosec


@log_decorator(_logger, level=logging.DEBUG)
async def retrieve_inputs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    port_keys: list[ServicePortKey],
    timeout_s: NonNegativeInt,
) -> RetrieveDataOutEnveloped:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("retrieve_inputs"),
        node_id=node_id,
        port_keys=port_keys,
        timeout_s=timeout_s,
    )
    assert isinstance(result, RetrieveDataOutEnveloped)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def update_projects_networks(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, project_id: ProjectID
) -> None:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("update_projects_networks"),
        project_id=project_id,
        timeout_s=_RPC_DEFAULT_TIMEOUT_S,
    )
    assert result is None  # nosec
