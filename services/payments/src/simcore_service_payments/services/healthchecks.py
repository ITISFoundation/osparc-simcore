import asyncio
import logging

from fastapi import FastAPI
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


async def _monitor_liveness():
    #
    #
    # logs with specific format so graylog can send alarm if found
    #
    #
    raise NotImplementedError


async def _periodic():
    while True:
        # do something
        await _monitor_liveness()
        # what if fails?, wait&repeat or stop-forever or cleanup&restart ?


def setup_healthchecks(app: FastAPI):
    # setup _monitor_liveness as a periodic task in only one of the replicas

    async def _on_startup() -> None:
        ...

    async def _on_shutdown() -> None:
        ...

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
