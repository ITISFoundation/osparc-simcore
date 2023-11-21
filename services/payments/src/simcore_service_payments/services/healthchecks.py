import asyncio
import logging

from models_library.healthchecks import LivenessResult
from sqlalchemy.ext.asyncio import AsyncEngine

from .payments_gateway import PaymentsGatewayApi
from .postgres import check_postgres_liveness
from .resource_usage_tracker import ResourceUsageTrackerApi

_logger = logging.getLogger(__name__)


async def create_health_report(
    gateway: PaymentsGatewayApi,
    rut: ResourceUsageTrackerApi,
    engine: AsyncEngine,
) -> dict[str, LivenessResult]:
    gateway_liveness, rut_liveness, db_liveness = await asyncio.gather(
        gateway.check_liveness(), rut.check_liveness(), check_postgres_liveness(engine)
    )

    return {
        "payments_gateway": gateway_liveness,
        "resource_usage_tracker": rut_liveness,
        "postgres": db_liveness,
    }
