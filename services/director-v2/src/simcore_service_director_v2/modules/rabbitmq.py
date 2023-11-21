import logging
from functools import partial
from typing import cast

from fastapi import FastAPI
from models_library.rabbitmq_messages import (
    CreditsLimit,
    WalletCreditsLimitReachedMessage,
)
from servicelib.rabbitmq import (
    RabbitMQClient,
    RabbitMQRPCClient,
    wait_till_rabbitmq_responsive,
)
from settings_library.rabbit import RabbitSettings

from ..core.errors import ConfigurationError
from ..core.settings import AppSettings

_logger = logging.getLogger(__name__)


async def message_handler(app: FastAPI, data: bytes) -> bool:
    message = WalletCreditsLimitReachedMessage.parse_raw(data)

    scheduler: "DynamicSidecarsScheduler" = app.state.dynamic_sidecar_scheduler  # type: ignore[name-defined] # noqa: F821
    settings: AppSettings = app.state.settings

    if (
        settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_IGNORE_SERVICES_SHUTDOWN_WHEN_CREDITS_LIMIT_REACHED
    ):
        await scheduler.mark_all_services_in_wallet_for_removal(
            wallet_id=message.wallet_id
        )
    else:
        _logger.debug("Skipped shutting down services for wallet %s", message.wallet_id)

    return True


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: RabbitSettings = app.state.settings.DIRECTOR_V2_RABBITMQ
        await wait_till_rabbitmq_responsive(settings.dsn)
        app.state.rabbitmq_client = RabbitMQClient(
            client_name="director-v2", settings=settings
        )
        app.state.rabbitmq_rpc_client = await RabbitMQRPCClient.create(
            client_name="director-v2", settings=settings
        )

        await app.state.rabbitmq_client.subscribe(
            WalletCreditsLimitReachedMessage.get_channel_name(),
            partial(message_handler, app),
            topics=[f"*.{CreditsLimit.SHUTDOWN_SERVICES}"],
        )

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()
        if app.state.rabbitmq_rpc_client:
            await app.state.rabbitmq_rpc_client.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not hasattr(app.state, "rabbitmq_client"):
        msg = "RabbitMQ client is not available. Please check the configuration."
        raise ConfigurationError(msg)
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
    if not hasattr(app.state, "rabbitmq_rpc_client"):
        msg = (
            "RabbitMQ client for RPC is not available. Please check the configuration."
        )
        raise ConfigurationError(msg)
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)
