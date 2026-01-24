import logging

from fastapi import FastAPI
from models_library.notifications_errors import NotificationsTemplateNotFoundError
from models_library.rpc.notifications.template import (
    NotificationsTemplatePreviewRpcRequest,
    NotificationsTemplatePreviewRpcResponse,
    NotificationsTemplateRefRpc,
    NotificationsTemplateRpcResponse,
)
from servicelib.rabbitmq import RPCRouter

from ...models.template import TemplateRef
from .dependencies import get_notifications_templates_service

router = RPCRouter()

_logger = logging.getLogger(__name__)


@router.expose(reraise_if_error_type=(NotificationsTemplateNotFoundError,))
async def preview_template(
    _app: FastAPI,
    *,
    request: NotificationsTemplatePreviewRpcRequest,
) -> NotificationsTemplatePreviewRpcResponse:
    service = get_notifications_templates_service()

    _logger.error({"request": request})

    preview = service.preview_template(
        template_ref=TemplateRef(**request.ref.model_dump()),
        context=request.context,
    )

    _logger.info("Rendered preview for template %s: %s", request.ref, preview)

    template_ref = TemplateRef(**request.ref.model_dump())
    raise NotificationsTemplateNotFoundError(template_ref=template_ref)


@router.expose()
async def search_templates(
    _app: FastAPI,
    *,
    channel: str,
    template_name: str,
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
