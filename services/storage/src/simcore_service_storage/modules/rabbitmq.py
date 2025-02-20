import logging
from contextlib import suppress
from typing import cast

from fastapi import FastAPI
from models_library.osparc_jobs import OsparcJobId
from models_library.progress_bar import ProgressReport
from models_library.rabbitmq_messages import (
    ProgressRabbitMessageWorkerJob,
    ProgressType,
    RabbitMessageBase,
)
from models_library.users import UserID
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import (
    RabbitMQClient,
    RabbitMQRPCClient,
    wait_till_rabbitmq_responsive,
)
from settings_library.rabbit import RabbitSettings

from ..exceptions.errors import ConfigurationError

_logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg="Storage startup Rabbitmq",
        ):
            app.state.rabbitmq_client = None
            rabbit_settings: RabbitSettings | None = app.state.settings.STORAGE_RABBITMQ
            if not rabbit_settings:
                raise ConfigurationError(
                    msg="RabbitMQ client is de-activated in the settings"
                )
            await wait_till_rabbitmq_responsive(rabbit_settings.dsn)
            app.state.rabbitmq_client = RabbitMQClient(
                client_name="storage", settings=rabbit_settings
            )
            app.state.rabbitmq_rpc_server = await RabbitMQRPCClient.create(
                client_name="storage_rpc_server", settings=rabbit_settings
            )

    async def on_shutdown() -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg="Storage shutdown Rabbitmq",
        ):
            if app.state.rabbitmq_client:
                await app.state.rabbitmq_client.close()
            if app.state.rabbitmq_rpc_server:
                await app.state.rabbitmq_rpc_server.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not hasattr(app.state, "rabbitmq_client"):
        raise ConfigurationError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_rabbitmq_rpc_server(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_server  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_server)


async def post_message(app: FastAPI, message: RabbitMessageBase) -> None:
    with log_catch(_logger, reraise=False), suppress(ConfigurationError):
        # NOTE: if rabbitmq was not initialized the error does not need to flood the logs
        await get_rabbitmq_client(app).publish(message.channel_name, message)


async def post_task_progress_message(
    app: FastAPI, user_id: UserID, osparc_job_id: OsparcJobId, report: ProgressReport
) -> None:
    with log_catch(_logger, reraise=False):
        message = ProgressRabbitMessageWorkerJob.model_construct(
            user_id=user_id,
            osparc_job_id=osparc_job_id,
            progress_type=ProgressType.WORKER_JOB_EXPORTING,
            report=report,
        )
        await post_message(app, message)
