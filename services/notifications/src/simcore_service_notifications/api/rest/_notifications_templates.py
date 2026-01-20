from typing import Annotated, Any

from fastapi import APIRouter, Depends

from ...services.notifications_templates_service import NotificationsTemplatesService
from .dependencies import get_notifications_templates_service

router = APIRouter(prefix="/templates")


@router.post("/{template_name}:preview")
def preview_template(
    template_name: str,
    channel_name: str,
    variables: dict[str, Any],
    service: Annotated[NotificationsTemplatesService, Depends(get_notifications_templates_service)],
):
    variables |= {"product": {"ui": {"strong_color": None}}}

    return service.preview_template(template_name, channel_name, variables)
