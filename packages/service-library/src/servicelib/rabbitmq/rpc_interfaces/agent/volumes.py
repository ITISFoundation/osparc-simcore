import logging
from datetime import timedelta
from typing import Final

from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from pydantic import NonNegativeInt, TypeAdapter
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT: Final[NonNegativeInt] = int(timedelta(minutes=60).total_seconds())


@log_decorator(_logger, level=logging.DEBUG)
async def remove_volumes_without_backup_for_service(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    docker_node_id: str,
    swarm_stack_name: str,
    node_id: NodeID,
) -> None:
    result = await rabbitmq_rpc_client.request(
        RPCNamespace.from_entries(
            {
                "service": "agent",
                "docker_node_id": docker_node_id,
                "swarm_stack_name": swarm_stack_name,
            }
        ),
        TypeAdapter(RPCMethodName).validate_python(
            "remove_volumes_without_backup_for_service"
        ),
        node_id=node_id,
        timeout_s=_REQUEST_TIMEOUT,
    )
    assert result is None  # nosec


@log_decorator(_logger, level=logging.DEBUG)
async def backup_and_remove_volumes_for_all_services(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    docker_node_id: str,
    swarm_stack_name: str,
) -> None:
    result = await rabbitmq_rpc_client.request(
        RPCNamespace.from_entries(
            {
                "service": "agent",
                "docker_node_id": docker_node_id,
                "swarm_stack_name": swarm_stack_name,
            }
        ),
        TypeAdapter(RPCMethodName).validate_python(
            "backup_and_remove_volumes_for_all_services"
        ),
        timeout_s=_REQUEST_TIMEOUT,
    )
    assert result is None  # nosec
