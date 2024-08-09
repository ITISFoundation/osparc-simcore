import logging
from collections.abc import AsyncIterator
from typing import Final, cast

from aiohttp import web
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG
from servicelib.aiohttp.application_keys import (
    APP_RABBITMQ_CLIENT_KEY,
    APP_RABBITMQ_RPC_SERVER_KEY,
)
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import (
    RabbitMQClient,
    RabbitMQRPCClient,
    wait_till_rabbitmq_responsive,
)

from .rabbitmq_settings import RabbitSettings, get_plugin_settings
from .rest.healthcheck import HealthCheck, HealthCheckError

_logger = logging.getLogger(__name__)

_RPC_CLIENT_KEY: Final[str] = f"{__name__}.RabbitMQRPCClient"


async def _on_healthcheck_async_adapter(app: web.Application) -> None:
    rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
    if not rabbit_client.healthy:
        raise HealthCheckError(RABBITMQ_CLIENT_UNHEALTHY_MSG)


async def _rabbitmq_client_cleanup_ctx(app: web.Application) -> AsyncIterator[None]:
    settings: RabbitSettings = get_plugin_settings(app)
    with log_context(
        _logger, logging.INFO, msg=f"Check RabbitMQ backend is ready on {settings.dsn}"
    ):
        await wait_till_rabbitmq_responsive(f"{settings.dsn}")

    with log_context(
        _logger, logging.INFO, msg=f"Connect RabbitMQ clients to {settings.dsn}"
    ):
        app[APP_RABBITMQ_CLIENT_KEY] = RabbitMQClient("webserver", settings)
        app[APP_RABBITMQ_RPC_SERVER_KEY] = await RabbitMQRPCClient.create(
            client_name="webserver_rpc_server", settings=settings
        )

    # injects healthcheck
    healthcheck: HealthCheck = app[HealthCheck.__name__]
    healthcheck.on_healthcheck.append(_on_healthcheck_async_adapter)

    yield

    # cleanup
    with log_context(_logger, logging.INFO, msg="Close RabbitMQ client"):
        await app[APP_RABBITMQ_CLIENT_KEY].close()
        await app[APP_RABBITMQ_RPC_SERVER_KEY].close()


async def _rabbitmq_rpc_client_lifespan(app: web.Application):
    settings: RabbitSettings = get_plugin_settings(app)
    rpc_client = await RabbitMQRPCClient.create(
        client_name="webserver_rpc_client", settings=settings
    )

    assert rpc_client  # nosec

    app[_RPC_CLIENT_KEY] = rpc_client

    yield

    await rpc_client.close()


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_RABBITMQ",
    logger=_logger,
    depends=[],
)
def setup_rabbitmq(app: web.Application) -> None:
    app.cleanup_ctx.append(_rabbitmq_client_cleanup_ctx)
    app.cleanup_ctx.append(_rabbitmq_rpc_client_lifespan)


def get_rabbitmq_rpc_client(app: web.Application) -> RabbitMQRPCClient:
    return cast(RabbitMQRPCClient, app[_RPC_CLIENT_KEY])


def get_rabbitmq_client(app: web.Application) -> RabbitMQClient:
    return cast(RabbitMQClient, app[APP_RABBITMQ_CLIENT_KEY])


def get_rabbitmq_rpc_server(app: web.Application) -> RabbitMQRPCClient:
    return cast(RabbitMQRPCClient, app[APP_RABBITMQ_RPC_SERVER_KEY])
