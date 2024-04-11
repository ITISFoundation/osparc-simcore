import logging

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)
from servicelib.fastapi.rabbitmq import get_rabbitmq_client
from servicelib.rabbitmq import RabbitMQClient, wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings
from simcore_service_api_server.api.dependencies.rabbitmq import get_log_distributor
from simcore_service_api_server.core.health_checker import ApiServerHealthChecker

from ..services.log_streaming import LogDistributor

_logger = logging.getLogger(__name__)


def setup_rabbitmq(app: FastAPI) -> None:
    settings: RabbitSettings = app.state.settings.API_SERVER_RABBITMQ
    app.state.rabbitmq_client = None
    app.state.log_distributor = None

    instrumentator: Instrumentator | None = None
    if app.state.settings.API_SERVER_PROMETHEUS_INSTRUMENTATION_ENABLED:
        instrumentator = setup_prometheus_instrumentation(app)

    async def _on_startup() -> None:
        await wait_till_rabbitmq_responsive(settings.dsn)

        app.state.rabbitmq_client = RabbitMQClient(
            client_name="api_server", settings=settings
        )
        app.state.log_distributor = LogDistributor(app.state.rabbitmq_client)
        await app.state.log_distributor.setup()
        if instrumentator:
            app.state.health_checker = ApiServerHealthChecker(
                registry=instrumentator.registry,
                log_distributor=get_log_distributor(app),
                rabbit_client=get_rabbitmq_client(app),
                timeout_seconds=app.state.settings.API_SERVER_HEALTH_CHECK_TASK_TIMEOUT_SECONDS,
                allowed_health_check_failures=app.state.settings.API_SERVER_ALLOWED_HEALTH_CHECK_FAILURES,
            )
            await app.state.health_checker.setup(
                app.state.settings.API_SERVER_HEALTH_CHECK_TASK_PERIOD_SECONDS
            )

    async def _on_shutdown() -> None:
        if app.state.health_checker:
            await app.state.health_checker.teardown(
                timeout_seconds=app.state.settings.API_SERVER_HEALTH_CHECK_TASK_TIMEOUT_SECONDS
            )
        if app.state.log_distributor:
            await app.state.log_distributor.teardown()
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
