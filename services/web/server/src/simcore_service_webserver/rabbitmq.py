import logging
from collections.abc import AsyncIterator

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_RABBITMQ_CLIENT_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQClient, wait_till_rabbitmq_responsive

from .rabbitmq_settings import RabbitSettings, get_plugin_settings
from .rest.healthcheck import HealthCheck, HealthCheckError

_logger = logging.getLogger(__name__)


async def _on_healthcheck_async_adapter(app: web.Application) -> None:
    rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
    if not rabbit_client.healthy:
        msg = "RabbitMQ client is in a bad state! TIP: check if network was cut between server and clients?"
        raise HealthCheckError(msg)


async def _rabbitmq_client_cleanup_ctx(app: web.Application) -> AsyncIterator[None]:
    settings: RabbitSettings = get_plugin_settings(app)
    with log_context(
        _logger, logging.INFO, msg=f"Check RabbitMQ backend is ready on {settings.dsn}"
    ):
        await wait_till_rabbitmq_responsive(f"{settings.dsn}")

    with log_context(
        _logger, logging.INFO, msg=f"Connect RabbitMQ client to {settings.dsn}"
    ):
        app[APP_RABBITMQ_CLIENT_KEY] = RabbitMQClient("webserver", settings)

    # injects healthcheck
    healthcheck: HealthCheck = app[HealthCheck.__name__]
    healthcheck.on_healthcheck.append(_on_healthcheck_async_adapter)

    yield

    # cleanup
    with log_context(_logger, logging.INFO, msg="Close RabbitMQ client"):
        await app[APP_RABBITMQ_CLIENT_KEY].close()


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_RABBITMQ",
    logger=_logger,
    depends=[],
)
def setup_rabbitmq(app: web.Application) -> None:
    app.cleanup_ctx.append(_rabbitmq_client_cleanup_ctx)


def get_rabbitmq_client(app: web.Application) -> RabbitMQClient:
    return app[APP_RABBITMQ_CLIENT_KEY]
