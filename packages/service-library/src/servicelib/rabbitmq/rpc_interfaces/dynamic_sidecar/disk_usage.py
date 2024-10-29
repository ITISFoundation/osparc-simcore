import logging

from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from pydantic import parse_obj_as
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


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
        rpc_namespace, parse_obj_as(RPCMethodName, "update_disk_usage"), usage=usage
    )
    assert result is None  # nosec
