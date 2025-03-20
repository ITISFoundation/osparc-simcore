import logging

from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter

from .....logging_utils import log_decorator
from .....rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def ping(
    rabbitmq_rpc_client: RabbitMQRPCClient,
) -> str:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("ping"),
    )
    assert isinstance(result, str)  # nosec
    return result
