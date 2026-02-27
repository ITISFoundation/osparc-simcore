import logging

from models_library.notifications.rpc import NOTIFICATIONS_RPC_NAMESPACE, SendMessageFromTemplateRequest
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter, validate_call

from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
@validate_call(config={"arbitrary_types_allowed": True})
async def send_message_from_template(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    request: SendMessageFromTemplateRequest,
) -> None:
    await rabbitmq_rpc_client.request(
        NOTIFICATIONS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("send_message_from_template"),
        request=request,
    )
