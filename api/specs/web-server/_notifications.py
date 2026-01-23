# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_notifications.template import NotificationsTemplateGet
from models_library.api_schemas_webserver.notifications import SearchTemplatesQueryParams
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "notifications",
    ],
)


@router.get(
    "/notifications/templates:search",
    response_model=Envelope[list[NotificationsTemplateGet]],
)
async def search_templates(
    _query: Annotated[SearchTemplatesQueryParams, Depends()],
): ...
