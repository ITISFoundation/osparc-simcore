import logging

from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.services import ServiceOutput
from pydantic import TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient
from ._utils import get_rpc_namespace

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def toggle_ports_io(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    enable_outputs: bool,
    enable_inputs: bool
) -> None:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("toggle_ports_io"),
        enable_outputs=enable_outputs,
        enable_inputs=enable_inputs,
    )
    assert result is None  # nosec


@log_decorator(_logger, level=logging.DEBUG)
async def create_output_dirs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    node_id: NodeID,
    outputs_labels: dict[str, ServiceOutput]
) -> None:
    rpc_namespace = get_rpc_namespace(node_id)
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("create_output_dirs"),
        outputs_labels=outputs_labels,
    )
    assert result is None  # nosec
