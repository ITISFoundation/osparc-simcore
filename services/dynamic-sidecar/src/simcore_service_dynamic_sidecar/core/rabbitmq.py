import logging
from functools import lru_cache
from typing import cast

from fastapi import FastAPI
from models_library.progress_bar import ProgressReport
from models_library.rabbitmq_messages import (
    DynamicServiceRunningMessage,
    EventRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressType,
    RabbitEventMessageType,
    RabbitMessageBase,
    RabbitResourceTrackingMessages,
)
from servicelib.logging_utils import LogLevelInt, LogMessageStr, log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient, is_rabbitmq_responsive
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings

from ..core.settings import ApplicationSettings
from ..modules.service_liveness import wait_for_service_liveness

_logger = logging.getLogger(__file__)


async def _post_rabbit_message(app: FastAPI, message: RabbitMessageBase) -> None:
    with log_catch(_logger, reraise=False):
        await get_rabbitmq_client(app).publish(message.channel_name, message)


async def post_resource_tracking_message(
    app: FastAPI, message: RabbitResourceTrackingMessages
):
    await _post_rabbit_message(app, message)


async def post_dynamic_service_running_message(
    app: FastAPI, message: DynamicServiceRunningMessage
):
    await _post_rabbit_message(app, message)


async def post_log_message(
    app: FastAPI, log: LogMessageStr, *, log_level: LogLevelInt
) -> None:
    app_settings: ApplicationSettings = app.state.settings
    message = LoggerRabbitMessage.model_construct(
        node_id=app_settings.DY_SIDECAR_NODE_ID,
        user_id=app_settings.DY_SIDECAR_USER_ID,
        project_id=app_settings.DY_SIDECAR_PROJECT_ID,
        messages=[log],
        log_level=log_level,
    )

    await _post_rabbit_message(app, message)


async def post_progress_message(
    app: FastAPI, progress_type: ProgressType, report: ProgressReport
) -> None:
    app_settings: ApplicationSettings = app.state.settings
    message = ProgressRabbitMessageNode.model_construct(
        node_id=app_settings.DY_SIDECAR_NODE_ID,
        user_id=app_settings.DY_SIDECAR_USER_ID,
        project_id=app_settings.DY_SIDECAR_PROJECT_ID,
        progress_type=progress_type,
        report=report,
    )
    await _post_rabbit_message(app, message)


async def post_sidecar_log_message(
    app: FastAPI, log: LogMessageStr, *, log_level: LogLevelInt
) -> None:
    await post_log_message(app, f"[sidecar] {log}", log_level=log_level)


async def post_event_reload_iframe(app: FastAPI) -> None:
    app_settings: ApplicationSettings = app.state.settings
    message = EventRabbitMessage(
        node_id=app_settings.DY_SIDECAR_NODE_ID,
        user_id=app_settings.DY_SIDECAR_USER_ID,
        project_id=app_settings.DY_SIDECAR_PROJECT_ID,
        action=RabbitEventMessageType.RELOAD_IFRAME,
    )
    await _post_rabbit_message(app, message)


async def wait_for_rabbitmq_liveness(app: FastAPI) -> None:
    app_settings: ApplicationSettings = app.state.settings
    rabbit_settings: RabbitSettings = app_settings.RABBIT_SETTINGS

    await wait_for_service_liveness(
        is_rabbitmq_responsive,
        service_name="RabbitMQ",
        endpoint=rabbit_settings.dsn,
        url=rabbit_settings.dsn,
    )


@lru_cache(maxsize=2)
def _is_rabbitmq_initialized(app: FastAPI, state_client_name: str) -> bool:
    return hasattr(app.state, state_client_name)


def _raise_if_not_initialized(app: FastAPI, state_client_name: str) -> None:
    if not _is_rabbitmq_initialized(app, state_client_name):
        msg = "RabbitMQ client is not available. Please check the configuration."
        raise RuntimeError(msg)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    _raise_if_not_initialized(app, "rabbitmq_client")
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_rabbitmq_rpc_server(app: FastAPI) -> RabbitMQRPCClient:
    _raise_if_not_initialized(app, "rabbitmq_rpc_server")
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_server)


def setup_rabbitmq(app: FastAPI) -> None:
    async def on_startup() -> None:
        app_settings: ApplicationSettings = app.state.settings
        assert app_settings.RABBIT_SETTINGS  # nosec
        settings = app_settings.RABBIT_SETTINGS

        with log_context(_logger, logging.INFO, msg="Create RabbitMQClient"):
            app.state.rabbitmq_client = RabbitMQClient(
                client_name=f"dynamic-sidecar_{app_settings.DY_SIDECAR_NODE_ID}",
                settings=settings,
            )
        with log_context(_logger, logging.INFO, msg="Create RabbitMQRPCClient"):
            app.state.rabbitmq_rpc_server = await RabbitMQRPCClient.create(
                client_name=f"dynamic-sidecar_rpc_{app_settings.DY_SIDECAR_NODE_ID}",
                settings=settings,
            )

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()
        if app.state.rabbitmq_rpc_server:
            await app.state.rabbitmq_rpc_server.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
