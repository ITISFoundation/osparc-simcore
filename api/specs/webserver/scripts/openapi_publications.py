
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
        "publication",
    ],
)



@router.post(
    '/publications/service-submission',
    response_model=None,
    responses={'default': {'model': PublicationsServiceSubmissionPostResponse}},
)
def service_submission() -> Union[None, PublicationsServiceSubmissionPostResponse]:
    """
    Submits a new service candidate
    """
    pass
