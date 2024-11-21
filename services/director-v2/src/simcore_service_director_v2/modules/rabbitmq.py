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
from .notifier import publish_shutdown_no_more_credits

_logger = logging.getLogger(__name__)


async def handler_out_of_credits(app: FastAPI, data: bytes) -> bool:
    message = WalletCreditsLimitReachedMessage.model_validate_json(data)

    scheduler: "DynamicSidecarsScheduler" = app.state.dynamic_sidecar_scheduler  # type: ignore[name-defined] # noqa: F821
    settings: AppSettings = app.state.settings

    if (
        settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_CLOSE_SERVICES_VIA_FRONTEND_WHEN_CREDITS_LIMIT_REACHED
    ):
        _logger.warning(
            "Notifying frontend to shutdown service: '%s' for user '%s' because wallet '%s' is out of credits.",
            message.node_id,
            message.user_id,
            message.wallet_id,
        )
        await publish_shutdown_no_more_credits(
            app,
            user_id=message.user_id,
            node_id=message.node_id,
            wallet_id=message.wallet_id,
        )
    else:
        await scheduler.mark_all_services_in_wallet_for_removal(
            wallet_id=message.wallet_id
        )

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
            partial(handler_out_of_credits, app),
            exclusive_queue=False,
            topics=[f"*.{CreditsLimit.OUT_OF_CREDITS}"],
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
        raise ConfigurationError(msg=msg)
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
    if not hasattr(app.state, "rabbitmq_rpc_client"):
        msg = (
            "RabbitMQ client for RPC is not available. Please check the configuration."
        )
        raise ConfigurationError(msg=msg)
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)
