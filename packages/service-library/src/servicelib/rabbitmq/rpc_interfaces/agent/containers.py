import logging
from datetime import timedelta
from typing import Final

from models_library.docker import DockerNodeID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from pydantic import NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ....rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT: Final[NonNegativeInt] = int(timedelta(minutes=60).total_seconds())


@log_decorator(_logger, level=logging.DEBUG)
async def force_container_cleanup(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    docker_node_id: DockerNodeID,
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
        TypeAdapter(RPCMethodName).validate_python("force_container_cleanup"),
        node_id=node_id,
        timeout_s=_REQUEST_TIMEOUT,
    )
    assert result is None  # nosec
