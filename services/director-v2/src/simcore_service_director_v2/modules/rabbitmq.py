import logging
from collections.abc import AsyncIterator
from functools import partial
from typing import TYPE_CHECKING, cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from models_library.rabbitmq_messages import (
    CreditsLimit,
    WalletCreditsLimitReachedMessage,
)
from servicelib.fastapi.rabbitmq_lifespan import (
    configure_rabbitmq_client,
    configure_rabbitmq_rpc_client,
)
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings

from ..core.errors import ConfigurationError
from ..core.settings import AppSettings
from .notifier import publish_shutdown_no_more_credits

if TYPE_CHECKING:
    from ..modules.dynamic_sidecar.scheduler import DynamicSidecarsScheduler

_logger = logging.getLogger(__name__)


async def handler_out_of_credits(app: FastAPI, data: bytes) -> bool:
    message = WalletCreditsLimitReachedMessage.model_validate_json(data)

    scheduler: "DynamicSidecarsScheduler" = app.state.dynamic_sidecar_scheduler  # noqa: UP037
    settings: AppSettings = app.state.settings

    if settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_CLOSE_SERVICES_VIA_FRONTEND_WHEN_CREDITS_LIMIT_REACHED:  # noqa: E501
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
        await scheduler.mark_all_services_in_wallet_for_removal(wallet_id=message.wallet_id)

    return True


async def _subscribe_out_of_credits_lifespan(app: FastAPI) -> AsyncIterator[None]:
    rabbitmq_client = get_rabbitmq_client(app)
    await rabbitmq_client.subscribe(
        WalletCreditsLimitReachedMessage.get_channel_name(),
        partial(handler_out_of_credits, app),
        exclusive_queue=False,
        topics=[f"*.{CreditsLimit.OUT_OF_CREDITS}"],
    )
    yield


def configure_rabbitmq(app_lifespan: LifespanManager, *, settings: RabbitSettings) -> None:
    configure_rabbitmq_client(app_lifespan, settings=settings, client_name="director-v2")
    # NOTE: connectivity was already awaited above; skip the redundant wait here
    configure_rabbitmq_rpc_client(
        app_lifespan, settings=settings, client_name="director-v2-rpc-client", wait_for_connectivity=False
    )
    app_lifespan.add(_subscribe_out_of_credits_lifespan)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not hasattr(app.state, "rabbitmq_client"):
        msg = "RabbitMQ client is not available. Please check the configuration."
        raise ConfigurationError(msg=msg)
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
    if not hasattr(app.state, "rabbitmq_rpc_client"):
        msg = "RabbitMQ client for RPC is not available. Please check the configuration."
        raise ConfigurationError(msg=msg)
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)
