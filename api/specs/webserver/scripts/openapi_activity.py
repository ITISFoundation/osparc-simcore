from fastapi import APIRouter
from models_library.api_schemas_webserver.activity import ActivityStatusDict
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "tasks",
    ],
)


@router.get(
    "/activity/status",
    response_model=Envelope[ActivityStatusDict],
    operation_id="get_activity_status",
)
def get_activity_status():
    pass
