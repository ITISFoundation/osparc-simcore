import logging

from models_library.api_schemas_dynamic_sidecar import DYNAMIC_SIDECAR_RPC_NAMESPACE
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import parse_obj_as
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient
from simcore_service_dynamic_sidecar.api.rpc._disk_usage import DiskUsage

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def update_disk_usage(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, usage: dict[str, DiskUsage]
) -> None:
    result = await rabbitmq_rpc_client.request(
        DYNAMIC_SIDECAR_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "update_disk_usage"),
        usage=usage,
    )
    assert result is None  # nosec
