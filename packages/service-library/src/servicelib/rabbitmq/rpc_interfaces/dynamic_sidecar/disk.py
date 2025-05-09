import logging

from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from pydantic import TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def free_reserved_disk_space(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
) -> None:
    rpc_namespace = RPCNamespace.from_entries(
        {"service": "dy-sidecar", "node_id": f"{node_id}"}
    )
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("free_reserved_disk_space"),
    )
    assert result is None  # nosec
