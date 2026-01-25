from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from models_library.api_schemas_notifications.preview import NotificationPreviewGet
from models_library.api_schemas_notifications.template import NotificationsTemplateGet
from models_library.notifications import ChannelType
from servicelib.celery.models import ExecutionMetadata, OwnerMetadata, TasksQueue
from servicelib.celery.task_manager import TaskManager

from ...models.template import TemplateRef
from ...services.templates_service import NotificationsTemplatesService
from .dependencies import get_notifications_templates_service, get_task_manager

router = APIRouter(prefix="/notifications")


@router.get("/templates:search")
async def search_templates(
    service: Annotated[NotificationsTemplatesService, Depends(get_notifications_templates_service)],
    channel: str | None = None,
    template_name: str | None = None,
) -> list[NotificationsTemplateGet]:
    templates = service.search_templates(channel=channel, template_name=template_name)

    return [
        NotificationsTemplateGet(
            **asdict(template),
            variables_schema=template.context_model.model_json_schema(),
        )
        for template in templates
    ]


@router.post("/{channel}/templates/{template_name}:preview")
async def preview_notification(
    service: Annotated[NotificationsTemplatesService, Depends(get_notifications_templates_service)],
    channel: ChannelType,
    template_name: str,
    variables: dict[str, Any],  # NOTE: validated against the template's variables model
) -> NotificationPreviewGet:
    template_ref = TemplateRef(channel=channel, template_name=template_name)

    variables |= {"product": {"ui": {"strong_color": None}}}  # GCR: move to client side

    return NotificationPreviewGet(**asdict(service.preview_template(template_ref, variables)))


@router.post("/send")
async def send_notification(
    task_manager: Annotated[TaskManager, Depends(get_task_manager)],
    message: dict[str, Any],
) -> None:
    await task_manager.submit_task(
        ExecutionMetadata(name="send_email", queue=TasksQueue.NOTIFICATIONS),
        owner_metadata=OwnerMetadata(owner="me"),
        message=message,
    )
