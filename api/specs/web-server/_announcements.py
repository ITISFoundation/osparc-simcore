# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import APIRouter
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.announcements._handlers import Announcement

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "announcements",
    ],
)


@router.get(
    "/announcements",
    response_model=Envelope[list[Announcement]],
)
async def list_announcements():
    ...
