
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.diagnostics._handlers import (
    AppStatusCheck,
    StatusDiagnosticsGet,
    StatusDiagnosticsQueryParam,
)
from simcore_service_webserver.rest.healthcheck import HealthInfoDict

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "tasks",
    ],
)




@router.get(
    '/activity/status',
    response_model=ActivityStatusGetResponse,
    responses={'default': {'model': ActivityStatusGetResponse1}},

)
def get_status() -> Union[ActivityStatusGetResponse, ActivityStatusGetResponse1]:
    pass
