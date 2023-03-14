import logging
from functools import partial
from typing import Optional, cast

from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import RPCNamespace, wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt

from ..core.errors import ConfigurationError
from ..core.settings import ApplicationSettings
from .concurrency import HandlerIsRunningError, LowPriorityHandlerManager
from .low_priority_managers import get_low_priority_managers
from .task_monitor import (
    disable_volume_removal_task,
    enable_volume_removal_task_if_missing,
)
from .volume_removal import remove_volumes as _remove_volumes

logger = logging.getLogger(__name__)


def _get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not app.state.rabbitmq_client:
        raise ConfigurationError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    return cast(RabbitMQClient, app.state.rabbitmq_client)


async def _safe_remove_volumes(
    app: FastAPI, volume_names: list[str], volume_remove_timeout_s: float
) -> None:
    volumes_cleanup_manager: LowPriorityHandlerManager = get_low_priority_managers(
        app
    ).volumes_cleanup

    # Below workflow allows for parallel volume remove requests to play nice with the
    # `volumes_cleanup` task that can be running at any time. The idea is to cancel
    # the task and give priority to the volume removal:
    # - case 1: `volumes_cleanup` task is running
    #   - the `deny_handler_usage` will raise an error
    #   - the `volumes_cleanup` task is unscheduled
    #   - any current backup of the volumes will be stopped
    #   - the `deny_handler_usage` will now work
    #   - the `volumes_cleanup` task will be blocked form running
    #   - PAYLOAD RUNS:
    #       - `volumes_cleanup` cannot possibly start
    #   - the `volumes_cleanup` task is scheduled once again
    # - case 2: `volumes_cleanup is not running`
    #   - the `deny_handler_usage` will NOT raise an error
    #   - the `volumes_cleanup` task will be blocked form running
    #   - PAYLOAD RUNS:
    #     - if the `volumes_cleanup` were to be triggered again it
    #       is blocked while this is running
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(2),
        retry=retry_if_exception_type(HandlerIsRunningError),
        reraise=True,
    ):
        with attempt:
            try:
                async with volumes_cleanup_manager.deny_handler_usage():
                    await _remove_volumes(
                        volume_names, volume_remove_timeout_s=volume_remove_timeout_s
                    )
            except HandlerIsRunningError:
                await disable_volume_removal_task(app)
                raise

    await enable_volume_removal_task_if_missing(app)


def setup(app: FastAPI) -> None:
    # NOTE: this is also the name of the handler called by the client
    remove_volumes = partial(_safe_remove_volumes, app=app)

    async def on_startup() -> None:
        app.state.rabbitmq_client = None
        settings: ApplicationSettings = app.state.settings
        rabbit_settings: Optional[RabbitSettings] = app.state.settings.AGENT_RABBITMQ
        if rabbit_settings is None:
            logger.warning("rabbitmq module is disabled")
            return

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
