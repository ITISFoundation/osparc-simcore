import logging

from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient
from ._utils import get_rpc_namespace

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def cleanup_local_long_running_tasks(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
) -> None:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("cleanup_local_long_running_tasks"),
    )
    assert result is None  # nosec
