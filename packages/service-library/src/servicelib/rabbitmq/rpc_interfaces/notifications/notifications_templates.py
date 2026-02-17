import logging

from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rpc.notifications import NOTIFICATIONS_RPC_NAMESPACE
from models_library.rpc.notifications.template import (
    TemplatePreviewRpcRequest,
    TemplatePreviewRpcResponse,
    TemplateRpcResponse,
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
    request: TemplatePreviewRpcRequest,
) -> TemplatePreviewRpcResponse:
    result = await rabbitmq_rpc_client.request(
        NOTIFICATIONS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("preview_template"),
        request=request,
    )
    return TypeAdapter(TemplatePreviewRpcResponse).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
@validate_call(config={"arbitrary_types_allowed": True})
async def search_templates(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    channel: str | None = None,
    template_name: str | None = None,
) -> list[TemplateRpcResponse]:
    result = await rabbitmq_rpc_client.request(
        NOTIFICATIONS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("search_templates"),
        channel=channel,
        template_name=template_name,
    )
    return TypeAdapter(list[TemplateRpcResponse]).validate_python(result)
