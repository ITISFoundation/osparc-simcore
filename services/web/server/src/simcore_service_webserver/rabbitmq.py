import logging
from typing import AsyncIterator

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_RABBITMQ_CLIENT_KEY
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import wait_till_rabbitmq_responsive

# TODO move this module or rname
from .computation_settings import RabbitSettings, get_plugin_settings

log = logging.getLogger(__name__)


def setup_rabbitmq_client(app: web.Application) -> AsyncIterator[None]:
    async def setup(app: web.Application):
        settings: RabbitSettings = get_plugin_settings(app)
        with log_context(
            log, logging.INFO, msg=f"Check RabbitMQ backend is ready on {settings.dsn}"
        ):
            await wait_till_rabbitmq_responsive(f"{settings.dsn}")

        with log_context(
            log, logging.INFO, msg=f"Connect RabbitMQ client to {settings.dsn}"
        ):
            app[APP_RABBITMQ_CLIENT_KEY] = RabbitMQClient("webserver", settings)

        yield

        # cleanup
        with log_context(log, logging.INFO, msg="Closing RabbitMQ client"):
            await app[APP_RABBITMQ_CLIENT_KEY].close()

    app.cleanup_ctx.append(setup)


def get_rabbitmq_client(app: web.Application) -> RabbitMQClient:
    return app[APP_RABBITMQ_CLIENT_KEY]
