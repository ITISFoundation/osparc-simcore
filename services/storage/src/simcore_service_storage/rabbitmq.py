from typing import cast

from aiohttp import web
from servicelib.rabbitmq._client import RabbitMQClient
from servicelib.rabbitmq._utils import wait_till_rabbitmq_responsive

from .constants import APP_CONFIG_KEY
from .settings import Settings

_APP_RABBITMQ_CLIENT_KEY = "APP_RABBITMQ_CLIENT_KEY"


async def _rabbitmq_client(app: web.Application):
    app[_APP_RABBITMQ_CLIENT_KEY] = None
    settings: Settings = app[APP_CONFIG_KEY]
    assert settings.STORAGE_RABBITMQ  # nosec
    rabbitmq_settings = settings.STORAGE_RABBITMQ

    await wait_till_rabbitmq_responsive(f"{rabbitmq_settings.dsn}")

    app[_APP_RABBITMQ_CLIENT_KEY] = RabbitMQClient("storage", rabbitmq_settings)

    yield

    await app[_APP_RABBITMQ_CLIENT_KEY].close()


def setup_rabbitmq(app: web.Application):
    if _rabbitmq_client not in app.cleanup_ctx:
        app.cleanup_ctx.append(_rabbitmq_client)


def get_rabbitmq_client(app: web.Application) -> RabbitMQClient:
    return cast(RabbitMQClient, app[_APP_RABBITMQ_CLIENT_KEY])
