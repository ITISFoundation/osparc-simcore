from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import PlainTextResponse

from ..modules.prometheus_metrics import UserServicesMetrics
from ._dependencies import get_user_services_metrics

router = APIRouter()


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "error in recovering data from user service"
        }
    },
)
async def metrics_endpoint(
    user_services_metrics: Annotated[
        UserServicesMetrics, Depends(get_user_services_metrics)
    ],
):
    """Exposes metrics form the underlying user service.

    Possible responses:
    - HTTP 200 & empty body: user services did not start
    - HTTP 200 & prometheus metrics: was able to fetch data from user service
    - HTTP 500 & error message: something went wrong when fetching data from user service
    """
    metrics_response = user_services_metrics.get_metrics()
    return PlainTextResponse(metrics_response.body, status_code=metrics_response.status)
