import logging
from typing import Any

from models_library.notifications._notifications import TemplateRef
from models_library.notifications.rpc import NOTIFICATIONS_RPC_NAMESPACE
from models_library.notifications.rpc.template import (
    PreviewTemplateRequest,
    PreviewTemplateResponse,
    SearchTemplatesResponse,
)
from models_library.notifications.rpc.template import (
    TemplateRef as TemplateRefRpc,
)
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter, validate_call

from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
@validate_call(config={"arbitrary_types_allowed": True})
async def preview_template(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    ref: TemplateRef,
    context: dict[str, Any],
) -> PreviewTemplateResponse:
    result = await rabbitmq_rpc_client.request(
        NOTIFICATIONS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("preview_template"),
        request=PreviewTemplateRequest(
            ref=TemplateRefRpc(**ref.model_dump()),
            context=context,
        ),
    )
    return TypeAdapter(PreviewTemplateResponse).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
@validate_call(config={"arbitrary_types_allowed": True})
async def search_templates(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    channel: str | None,
    template_name: str | None,
) -> list[SearchTemplatesResponse]:
    result = await rabbitmq_rpc_client.request(
        NOTIFICATIONS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("search_templates"),
        channel=channel,
        template_name=template_name,
    )
    return TypeAdapter(list[SearchTemplatesResponse]).validate_python(result)
