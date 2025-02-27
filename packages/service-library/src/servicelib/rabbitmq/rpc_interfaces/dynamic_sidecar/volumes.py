import logging

from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from models_library.sidecar_volumes import VolumeCategory, VolumeStatus
from pydantic import TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def save_volume_state(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    status: VolumeStatus,
    category: VolumeCategory,
) -> None:
    rpc_namespace = RPCNamespace.from_entries(
        {"service": "dy-sidecar", "node_id": f"{node_id}"}
    )
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("save_volume_state"),
        status=status,
        category=category,
    )
    assert result is None  # nosec
