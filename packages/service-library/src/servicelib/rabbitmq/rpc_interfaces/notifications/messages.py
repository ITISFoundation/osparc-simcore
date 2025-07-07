from typing import Final

from models_library.api_schemas_notifications import NOTIFICATIONS_RPC_NAMESPACE
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rpc.notifications.messages import NotificationMessage, Recipient
from pydantic import NonNegativeInt, TypeAdapter

from ... import RabbitMQRPCClient

_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 30


async def send_notification_message(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    message: NotificationMessage,
    recipients: list[Recipient],
) -> None:
    await rabbitmq_rpc_client.request(
        NOTIFICATIONS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("send_notification_message"),
        timeout_s=_DEFAULT_TIMEOUT_S,
        message=message,
        recipients=recipients,
    )
