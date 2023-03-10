import logging
from functools import partial
from typing import cast

from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import RPCNamespace, wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings

from ..core.errors import ConfigurationError
from ..core.settings import ApplicationSettings
from .task_monitor import disable_volume_removal_task
from .volume_removal import remove_volumes as _remove_volumes

logger = logging.getLogger(__name__)


def _get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not app.state.rabbitmq_client:
        raise ConfigurationError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    return cast(RabbitMQClient, app.state.rabbitmq_client)


async def _safe_remove_volumes(
    app: FastAPI,
    volume_names: list[str],
    volume_removal_attempts: float,
    sleep_between_attempts_s: float,
) -> None:
    async with disable_volume_removal_task(app):
        # TODO: a shared lock with the task is required
        # for multiple parallel requests for volume removals!!!
        await _remove_volumes(
            volume_names,
            volume_removal_attempts=volume_removal_attempts,
            sleep_between_attempts_s=sleep_between_attempts_s,
        )


def setup(app: FastAPI) -> None:
    # NOTE: this is also the name of the handler called by the client
    remove_volumes = partial(_safe_remove_volumes, app=app)

    async def on_startup() -> None:
        app.state.rabbitmq_client = None
        settings: ApplicationSettings = app.state.settings
        rabbit_settings: RabbitSettings = app.state.settings.AGENT_RABBITMQ
        await wait_till_rabbitmq_responsive(rabbit_settings.dsn)
        app.state.rabbitmq_client = RabbitMQClient(
            client_name="autoscaling", settings=rabbit_settings
        )

        # setup RPC backed
        await app.state.rabbitmq_client.rpc_initialize()
        rabbit_client = _get_rabbitmq_client(app)

        namespace = RPCNamespace.from_entries(
            {"service": "agent", "docker_node_id": settings.AGENT_DOCKER_NODE_ID}
        )
        await rabbit_client.rpc_register_handler(
            namespace=namespace,
            method_name="remove_volumes",
            handler=remove_volumes,
        )

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            rabbit_client = _get_rabbitmq_client(app)
            await rabbit_client.rpc_unregister_handler(handler=remove_volumes)

            await app.state.rabbitmq_client.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
