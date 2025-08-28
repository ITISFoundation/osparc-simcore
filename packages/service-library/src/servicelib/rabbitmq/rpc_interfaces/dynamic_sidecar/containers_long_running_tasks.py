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
async def pull_container_images(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("pull_container_images"),
        lrt_namespace=lrt_namespace,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def create_containers(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    containers_create: ContainersCreate,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("create_containers"),
        lrt_namespace=lrt_namespace,
        containers_create=containers_create,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def down_containers(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("down_containers"),
        lrt_namespace=lrt_namespace,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def restore_cotnainers_state(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("restore_cotnainers_state"),
        lrt_namespace=lrt_namespace,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def save_containers_state(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("save_containers_state"),
        lrt_namespace=lrt_namespace,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def pull_container_port_inputs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("pull_container_port_inputs"),
        lrt_namespace=lrt_namespace,
        port_keys=port_keys,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def pull_container_port_outputs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("pull_container_port_outputs"),
        lrt_namespace=lrt_namespace,
        port_keys=port_keys,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def push_container_port_outputs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("push_container_port_outputs"),
        lrt_namespace=lrt_namespace,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def restart_containers(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("restart_containers"),
        lrt_namespace=lrt_namespace,
    )
    assert isinstance(result, TaskId)  # nosec
    return result
