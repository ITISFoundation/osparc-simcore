from fastapi import FastAPI
from models_library.rpc.notifications.template import (
    NotificationsTemplateRefRpcGet,
    NotificationsTemplateRpcGet,
)
from servicelib.rabbitmq import RPCRouter

from .dependencies import get_notifications_templates_service

router = RPCRouter()


@router.expose()
async def search_templates(
    _app: FastAPI,
    *,
    channel: str,
    template_name: str,
) -> list[NotificationsTemplateRpcGet]:
    service = get_notifications_templates_service()
    templates = service.search_templates(channel=channel, template_name=template_name)

    return [
        NotificationsTemplateRpcGet(
            ref=NotificationsTemplateRefRpcGet(
                channel=template.ref.channel,
                template_name=template.ref.template_name,
            ),
            context_schema=template.context_model.model_json_schema(),
        )
        for template in templates
    ]
