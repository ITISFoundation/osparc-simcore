import logging

from models_library.api_schemas_directorv2.dynamic_services import ContainersCreate
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter

from servicelib.long_running_tasks.models import LRTNamespace, TaskId

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient
from ._utils import get_rpc_namespace

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def pull_user_services_images(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("pull_user_services_images"),
        lrt_namespace=lrt_namespace,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def create_user_services(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    containers_create: ContainersCreate,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("create_user_services"),
        lrt_namespace=lrt_namespace,
        containers_create=containers_create,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def remove_user_services(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("remove_user_services"),
        lrt_namespace=lrt_namespace,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def restore_user_services_state_paths(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("restore_user_services_state_paths"),
        lrt_namespace=lrt_namespace,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def save_user_services_state_paths(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("save_user_services_state_paths"),
        lrt_namespace=lrt_namespace,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def pull_user_services_input_ports(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("pull_user_services_input_ports"),
        lrt_namespace=lrt_namespace,
        port_keys=port_keys,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def pull_user_services_output_ports(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("pull_user_services_output_ports"),
        lrt_namespace=lrt_namespace,
        port_keys=port_keys,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def push_user_services_output_ports(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("push_user_services_output_ports"),
        lrt_namespace=lrt_namespace,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def restart_user_services(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("restart_user_services"),
        lrt_namespace=lrt_namespace,
    )
    assert isinstance(result, TaskId)  # nosec
    return result
