import logging
from typing import Final

from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from pydantic import TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient

_logger = logging.getLogger(__name__)

_UPDATE_DISK_USAGE: Final[RPCMethodName] = TypeAdapter(RPCMethodName).validate_python(
    "update_disk_usage"
)


@log_decorator(_logger, level=logging.DEBUG)
async def update_disk_usage(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    usage: dict[str, DiskUsage],
) -> None:
    rpc_namespace = RPCNamespace.from_entries(
        {"service": "dy-sidecar", "node_id": f"{node_id}"}
    )
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _UPDATE_DISK_USAGE,
        usage=usage,
    )
    assert result is None  # nosec
