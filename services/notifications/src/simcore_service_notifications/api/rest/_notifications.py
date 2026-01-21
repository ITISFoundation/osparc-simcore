from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from models_library.api_schemas_notifications.preview import NotificationPreviewGet
from models_library.api_schemas_notifications.template import NotificationTemplateGet

from ...models.template import TemplateRef
from ...services.templates_service import NotificationsTemplatesService
from .dependencies import get_notifications_templates_service

router = APIRouter(prefix="/notifications")


@router.get("/{channel}/templates")
def list_templates(
    channel: str,
    service: Annotated[NotificationsTemplatesService, Depends(get_notifications_templates_service)],
) -> list[NotificationTemplateGet]:
    templates = service.list_templates(channel)

    return [
        NotificationTemplateGet(
            **asdict(template),
            variables_schema=template.variables_model.model_json_schema(),
        )
        for template in templates
    ]


@router.post("/{channel}/templates/{template_name}:preview")
def preview_notification(
    channel: str,
    template_name: str,
    variables: dict[str, Any],
    service: Annotated[NotificationsTemplatesService, Depends(get_notifications_templates_service)],
) -> NotificationPreviewGet:
    template_ref = TemplateRef(channel=channel, template_name=template_name)

    variables |= {"product": {"ui": {"strong_color": None}}}  # GCR: move to client side

    return NotificationPreviewGet(**asdict(service.render_preview(template_ref, variables)))
