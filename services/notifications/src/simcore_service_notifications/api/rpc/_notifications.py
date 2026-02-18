import logging

from fastapi import FastAPI
from models_library.notifications import ChannelType
from models_library.notifications_errors import (
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
)
from models_library.rpc.notifications.template import (
    TemplatePreviewRpcRequest,
    TemplatePreviewRpcResponse,
    TemplateRefRpc,
    TemplateRpcResponse,
)
from servicelib.rabbitmq import RPCRouter

from ...models.template import TemplateRef
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
    request: TemplatePreviewRpcRequest,
) -> TemplatePreviewRpcResponse:
    service = get_notifications_templates_service()

    preview = service.preview_template(
        ref=TemplateRef(**request.ref.model_dump()),
        context=request.context,
    )

    return TemplatePreviewRpcResponse(
        ref=request.ref,
        message_content=preview.message_content.model_dump(),
    )


@router.expose()
async def search_templates(
    _app: FastAPI,
    *,
    channel: ChannelType | None,
    template_name: str | None,
) -> list[TemplateRpcResponse]:
    """
    Searches for notification templates based on the specified channel and template name.

    Args:
        _app: The FastAPI application instance.
        channel: The channel type to filter templates. Use `None` to search across all channels.
        template_name: The name of the template to search for.
            Use wildcards (e.g., `*`, `?`) for partial matches. `None` searches for all templates.

    Returns:
        A list of notification template responses matching the search criteria.
    """
    service = get_notifications_templates_service()
    templates = service.search_templates(channel=channel, template_name=template_name)

    return [
        TemplateRpcResponse(
            ref=TemplateRefRpc(
                channel=template.ref.channel,
                template_name=template.ref.template_name,
            ),
            context_schema=template.context_model.model_json_schema(),
        )
        for template in templates
    ]
