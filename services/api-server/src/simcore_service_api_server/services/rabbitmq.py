import logging

from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQClient, wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings

from ..api.dependencies.rabbitmq import JobLogDistributor

_logger = logging.getLogger(__name__)


def setup_rabbitmq(app: FastAPI) -> None:
    settings: RabbitSettings = app.state.settings.API_SERVER_RABBITMQ
    app.state.rabbitmq_client = None
    app.state.job_log_distributor = None

    async def _on_startup() -> None:
        await wait_till_rabbitmq_responsive(settings.dsn)

        app.state.rabbitmq_client = RabbitMQClient(
            client_name="api_server", settings=settings
        )
        app.state.job_log_distributor = JobLogDistributor(
            rabbit_client=app.state.rabbitmq_client
        )
        await app.state.job_log_distributor.setup()

    async def _on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()
        if app.state.job_log_distributor is not None:
            await app.state.job_log_distributor.teardown()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
