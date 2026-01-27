import logging

from fastapi import FastAPI
from models_library.notifications import ChannelType
from models_library.notifications_errors import (
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
)
from models_library.rpc.notifications.template import (
    NotificationsTemplatePreviewRpcRequest,
    NotificationsTemplatePreviewRpcResponse,
    NotificationsTemplateRefRpc,
    NotificationsTemplateRpcResponse,
)
from servicelib.rabbitmq import RPCRouter

from ...models.template import NotificationsTemplateRef
from .dependencies import get_notifications_templates_service

router = RPCRouter()

_logger = logging.getLogger(__name__)


@router.expose(
    reraise_if_error_type=(
        NotificationsTemplateContextValidationError,
        NotificationsTemplateNotFoundError,
    )
)
async def preview_template(
    _app: FastAPI,
    *,
    request: NotificationsTemplatePreviewRpcRequest,
) -> NotificationsTemplatePreviewRpcResponse:
    service = get_notifications_templates_service()

    preview = service.preview_template(
        ref=NotificationsTemplateRef(**request.ref.model_dump()),
        context=request.context,
    )

    return NotificationsTemplatePreviewRpcResponse(
        ref=request.ref,
        content=preview.content.model_dump(),
    )


@router.expose()
async def search_templates(
    _app: FastAPI,
    *,
    channel: ChannelType | None,
    template_name: str | None,
) -> list[NotificationsTemplateRpcResponse]:
    service = get_notifications_templates_service()
    templates = service.search_templates(channel=channel, template_name=template_name)

    return [
        NotificationsTemplateRpcResponse(
            ref=NotificationsTemplateRefRpc(
                channel=template.ref.channel,
                template_name=template.ref.template_name,
            ),
            context_schema=template.context_model.model_json_schema(),
        )
        for template in templates
    ]
