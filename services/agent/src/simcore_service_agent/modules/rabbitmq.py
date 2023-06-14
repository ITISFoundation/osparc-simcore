import logging
from functools import partial

from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import (
    RPCMethodName,
    RPCNamespace,
    wait_till_rabbitmq_responsive,
)
from settings_library.rabbit import RabbitSettings

from ..core.errors import ConfigurationError
from ..core.settings import ApplicationSettings
from .volumes_cleanup import (
    SidecarVolumes,
    get_sidecar_volumes_list,
    remove_sidecar_volumes,
)

logger = logging.getLogger(__name__)


def _get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not app.state.rabbitmq_client:
        raise ConfigurationError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    rabbit_mq_client: RabbitMQClient = app.state.rabbitmq_client
    return rabbit_mq_client


async def _safe_remove_volumes(
    app: FastAPI, volume_names: list[str], volume_remove_timeout_s: float
) -> None:
    sidecar_volumes: list[SidecarVolumes] = get_sidecar_volumes_list(
        [{"Name": x} for x in volume_names]
    )
    await remove_sidecar_volumes(app, sidecar_volumes, volume_remove_timeout_s)


def setup(app: FastAPI) -> None:
    # NOTE: this is also the name of the handler called by the client
    remove_volumes = partial(_safe_remove_volumes, app=app)

    async def on_startup() -> None:
        app.state.rabbitmq_client = None
        settings: ApplicationSettings = app.state.settings
        rabbit_settings: RabbitSettings | None = app.state.settings.AGENT_RABBITMQ
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
            {
                "service": "agent",
                "docker_node_id": settings.AGENT_DOCKER_NODE_ID,
                "swarm_stack_name": settings.AGENT_VOLUMES_CLEANUP_TARGET_SWARM_STACK_NAME,
            }
        )
        await rabbit_client.rpc_register_handler(
            namespace=namespace,
            method_name=RPCMethodName("remove_volumes"),
            handler=remove_volumes,
        )

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            rabbit_client = _get_rabbitmq_client(app)

            await rabbit_client.rpc_unregister_handler(handler=remove_volumes)
            await app.state.rabbitmq_client.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
