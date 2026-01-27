# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_webserver.notifications import (
    NotificationsMessageBody,
    NotificationsTemplateGet,
    NotificationsTemplatePreviewBody,
    NotificationsTemplatePreviewGet,
    SearchTemplatesQueryParams,
)
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "notifications",
    ],
)


@router.post(
    "/notifications/messages:send",
    response_model=Envelope[TaskGet],
)
async def send_message(
    _body: NotificationsMessageBody,
): ...


@router.post(
    "/notifications/templates:preview",
    response_model=Envelope[NotificationsTemplatePreviewGet],
)
async def preview_template(
    _body: NotificationsTemplatePreviewBody,
): ...


@router.get(
    "/notifications/templates:search",
    response_model=Envelope[list[NotificationsTemplateGet]],
)
async def search_templates(
    _query: Annotated[SearchTemplatesQueryParams, Depends()],
):
    """
    Search for available notification templates by channel and/or template name.
    Both channel and template_name support wildcard patterns for flexible matching.

    Returns templates with their context schema defining required variables for rendering.
    """
