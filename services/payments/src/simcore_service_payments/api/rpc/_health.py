import logging

from fastapi import FastAPI
from models_library.healthchecks import LivenessResult
from servicelib.rabbitmq import RPCRouter

from ...services.healthchecks import create_health_report
from ...services.payments_gateway import PaymentsGatewayApi
from ...services.postgres import get_engine
from ...services.resource_usage_tracker import ResourceUsageTrackerApi

_logger = logging.getLogger(__name__)


router = RPCRouter()


@router.expose()
async def check_health(
    app: FastAPI,
) -> dict[str, LivenessResult]:
    return await create_health_report(
        gateway=PaymentsGatewayApi.get_from_app_state(app),
        rut=ResourceUsageTrackerApi.get_from_app_state(app),
        engine=get_engine(app),
    )
