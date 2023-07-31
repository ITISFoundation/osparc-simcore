# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from fastapi import APIRouter, FastAPI
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.studies_dispatcher._rest_handlers import (
    ServiceGet,
    Viewer,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "nih-sparc",
    ],
)


@router.get(
    "/services",
    response_model=Envelope[list[ServiceGet]],
    operation_id="list_latest_services",
)
async def list_latest_services():
    """Returns a list latest version of services"""


@router.get(
    "/viewers",
    response_model=Envelope[list[Viewer]],
    operation_id="list_viewers",
)
async def list_viewers(file_type: str | None = None):
    """Lists all publically available viewers

    Notice that this might contain multiple services for the same filetype

    If file_type is provided, then it filters viewer for that filetype
    """


@router.get(
    "/viewers/default",
    response_model=Envelope[list[Viewer]],
    operation_id="list_default_viewers",
)
async def list_default_viewers(file_type: str | None = None):
    """Lists the default viewer for each supported filetype

    This was interfaced as a subcollection of viewers because it is a very common use-case

    Only publicaly available viewers

    If file_type is provided, then it filters viewer for that filetype
    """


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_and_save_openapi_specs

    create_and_save_openapi_specs(
        FastAPI(routes=router.routes), CURRENT_DIR.parent / "openapi-nih-sparc.yaml"
    )
