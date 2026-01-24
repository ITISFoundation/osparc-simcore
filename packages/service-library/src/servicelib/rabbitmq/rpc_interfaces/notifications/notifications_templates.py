import logging
from typing import cast

from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rpc.notifications import NOTIFICATIONS_RPC_NAMESPACE
from models_library.rpc.notifications.template import (
    NotificationsTemplatePreviewRpcRequest,
    NotificationsTemplatePreviewRpcResponse,
    NotificationsTemplateRpcResponse,
)
from pydantic import TypeAdapter, validate_call
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
@validate_call(config={"arbitrary_types_allowed": True})
async def preview_template(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    request: NotificationsTemplatePreviewRpcRequest,
) -> NotificationsTemplatePreviewRpcResponse:
    _logger.error("Request: %s", request)

    result = await rabbitmq_rpc_client.request(
        NOTIFICATIONS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("preview_template"),
        request=request,
    )
    assert TypeAdapter(NotificationsTemplatePreviewRpcResponse).validate_python(result) is not None  # nosec
    return cast(NotificationsTemplatePreviewRpcResponse, result)


@log_decorator(_logger, level=logging.DEBUG)
@validate_call(config={"arbitrary_types_allowed": True})
async def search_templates(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    channel: str | None = None,
    template_name: str | None = None,
) -> list[NotificationsTemplateRpcResponse]:
    result = await rabbitmq_rpc_client.request(
        NOTIFICATIONS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("search_templates"),
        channel=channel,
        template_name=template_name,
    )
    assert TypeAdapter(list[NotificationsTemplateRpcResponse]).validate_python(result) is not None  # nosec
    return cast(list[NotificationsTemplateRpcResponse], result)
