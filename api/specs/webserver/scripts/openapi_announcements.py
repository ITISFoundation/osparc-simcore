""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import APIRouter, FastAPI
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
    operation_id="list_announcements",
)
async def list_announcements():
    ...


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_and_save_openapi_specs

    create_and_save_openapi_specs(
        FastAPI(routes=router.routes), CURRENT_DIR.parent / "openapi-announcements.yaml"
    )
