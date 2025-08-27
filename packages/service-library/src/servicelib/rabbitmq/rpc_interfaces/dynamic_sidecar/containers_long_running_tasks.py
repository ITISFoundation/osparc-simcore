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
async def pull_user_services_docker_images_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python(
            "pull_user_services_docker_images_task"
        ),
        lrt_namespace=lrt_namespace,
    )
    return TaskId(result)


@log_decorator(_logger, level=logging.DEBUG)
async def create_service_containers_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    containers_create: ContainersCreate,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("create_service_containers_task"),
        lrt_namespace=lrt_namespace,
        containers_create=containers_create,
    )
    return TaskId(result)


@log_decorator(_logger, level=logging.DEBUG)
async def runs_docker_compose_down_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("runs_docker_compose_down_task"),
        lrt_namespace=lrt_namespace,
    )
    return TaskId(result)


@log_decorator(_logger, level=logging.DEBUG)
async def state_restore_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("state_restore_task"),
        lrt_namespace=lrt_namespace,
    )
    return TaskId(result)


@log_decorator(_logger, level=logging.DEBUG)
async def state_save_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("state_save_task"),
        lrt_namespace=lrt_namespace,
    )
    return TaskId(result)


@log_decorator(_logger, level=logging.DEBUG)
async def ports_inputs_pull_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("ports_inputs_pull_task"),
        lrt_namespace=lrt_namespace,
        port_keys=port_keys,
    )
    return TaskId(result)


@log_decorator(_logger, level=logging.DEBUG)
async def ports_outputs_pull_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("ports_outputs_pull_task"),
        lrt_namespace=lrt_namespace,
        port_keys=port_keys,
    )
    return TaskId(result)


@log_decorator(_logger, level=logging.DEBUG)
async def ports_outputs_push_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("ports_outputs_push_task"),
        lrt_namespace=lrt_namespace,
    )
    return TaskId(result)


@log_decorator(_logger, level=logging.DEBUG)
async def containers_restart_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
) -> TaskId:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("containers_restart_task"),
        lrt_namespace=lrt_namespace,
    )
    return TaskId(result)
