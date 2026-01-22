from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from models_library.api_schemas_notifications.preview import NotificationPreviewGet
from models_library.api_schemas_notifications.template import NotificationTemplateGet
from servicelib.celery.models import ExecutionMetadata, OwnerMetadata, TasksQueue

from ...clients.celery import get_task_manager
from ...models.channel import ChannelType
from ...models.template import TemplateRef
from ...services.templates_service import NotificationsTemplatesService
from .dependencies import get_notifications_templates_service

router = APIRouter(prefix="/notifications")


@router.get("/templates:search")
async def search_templates(
    service: Annotated[NotificationsTemplatesService, Depends(get_notifications_templates_service)],
    channel: str | None = None,
    template_name: str | None = None,
) -> list[NotificationTemplateGet]:
    templates = service.search_templates(channel=channel, template_name=template_name)

    return [
        NotificationTemplateGet(
            **asdict(template),
            variables_schema=template.variables_model.model_json_schema(),
        )
        for template in templates
    ]


@router.post("/{channel}/templates/{template_name}:preview")
async def preview_notification(
    channel: ChannelType,
    template_name: str,
    variables: dict[str, Any],  # NOTE: validated against the template's variables model
    service: Annotated[NotificationsTemplatesService, Depends(get_notifications_templates_service)],
) -> NotificationPreviewGet:
    template_ref = TemplateRef(channel=channel, template_name=template_name)

    variables |= {"product": {"ui": {"strong_color": None}}}  # GCR: move to client side

    return NotificationPreviewGet(**asdict(service.render_preview(template_ref, variables)))


@router.post("/send")
async def send_notification(
    request: Request,
    message: dict[str, Any],
) -> None:
    task_manager = get_task_manager(request.app)  # nosec
    await task_manager.submit_task(
        ExecutionMetadata(name="send_email", queue=TasksQueue.NOTIFICATIONS),
        owner_metadata=OwnerMetadata(owner="me"),
        message=message,
    )
