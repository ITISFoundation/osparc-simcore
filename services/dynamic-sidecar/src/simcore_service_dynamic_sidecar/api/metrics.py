from typing import Annotated

from fastapi import APIRouter, Depends

from ..modules.metrics import UserServicesMetrics
from ._dependencies import get_user_services_metrics

router = APIRouter()


@router.get("/metrics")
async def metrics_endpoint(
    user_services_metrics: Annotated[
        UserServicesMetrics, Depends(get_user_services_metrics)
    ],
):
    return user_services_metrics.get_metrics()
