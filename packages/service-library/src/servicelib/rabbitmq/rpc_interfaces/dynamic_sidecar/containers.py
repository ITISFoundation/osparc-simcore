import logging
from typing import Any

from models_library.api_schemas_directorv2.dynamic_services import ContainersComposeSpec
from models_library.api_schemas_dynamic_sidecar.containers import ActivityInfoOrNone
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient
from ._utils import get_rpc_namespace

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def create_compose_spec(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    containers_compose_spec: ContainersComposeSpec,
) -> None:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("create_compose_spec"),
        containers_compose_spec=containers_compose_spec,
    )
    assert result is None  # nosec


@log_decorator(_logger, level=logging.DEBUG)
async def containers_docker_inspect(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    only_status: bool,
) -> dict[str, Any]:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("containers_docker_inspect"),
        only_status=only_status,
    )
    assert isinstance(result, dict)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_containers_activity(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, node_id: NodeID
) -> ActivityInfoOrNone:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("get_containers_activity"),
    )
    return TypeAdapter(ActivityInfoOrNone).validate_python(result) if result else None


@log_decorator(_logger, level=logging.DEBUG)
async def get_containers_name(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, node_id: NodeID, filters: str
) -> str:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("get_containers_name"),
        filters=filters,
    )
    assert isinstance(result, str)
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def inspect_container(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, node_id: NodeID, container_id: str
) -> dict[str, Any]:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("inspect_container"),
        container_id=container_id,
    )
    assert isinstance(result, dict)
    return result
