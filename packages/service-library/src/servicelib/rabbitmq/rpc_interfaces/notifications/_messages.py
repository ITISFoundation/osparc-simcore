import logging
from typing import Any

from models_library.notifications.rpc import (
    NOTIFICATIONS_RPC_NAMESPACE,
    SendMessageRequest,
    SendMessageResponse,
)
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter, validate_call

from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
@validate_call(config={"arbitrary_types_allowed": True})
async def send_message(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    message: dict[str, Any],
) -> SendMessageResponse:
    result = await rabbitmq_rpc_client.request(
        NOTIFICATIONS_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("send_message"),
        request=SendMessageRequest(message=message),
    )
    assert isinstance(result, SendMessageResponse)  # nosec
    return result
