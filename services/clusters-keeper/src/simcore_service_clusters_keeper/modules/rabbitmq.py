import contextlib
import functools
import logging
from typing import Final, cast

from fastapi import FastAPI
from models_library.rabbitmq_messages import RabbitMessageBase
from pydantic import parse_obj_as
from servicelib.logging_utils import log_catch

from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient, RPCMethodName,RPCNamespace,wait_till_rabbitmq_responsive,

from settings_library.rabbit import RabbitSettings

from ..clusters_api import cluster_heartbeat, create_cluster
from ..core.errors import ConfigurationError
from ..core.settings import get_application_settings

logger = logging.getLogger(__name__)

CLUSTERS_KEEPER_RPC_NAMESPACE: Final[RPCNamespace] = parse_obj_as(
    RPCNamespace, "clusters-keeper"
)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.rabbitmq_client = None
        settings: RabbitSettings | None = get_application_settings(
            app
        ).CLUSTERS_KEEPER_RABBITMQ
        if not settings:
            logger.warning("Rabbit MQ client is de-activated in the settings")
            return
        await wait_till_rabbitmq_responsive(settings.dsn)
        app.state.rabbitmq_client = RabbitMQClient(
            client_name="clusters_keeper", settings=settings
        )
        app.state.rabbitmq_rpc_server = rpc_server = await RabbitMQRPCClient.create(
            client_name="clusters_keeper_rpc_server", settings=settings
        )


        await rpc_server.rpc_register_handler(
            CLUSTERS_KEEPER_RPC_NAMESPACE,
            RPCMethodName("cluster_heartbeat"),
            functools.partial(cluster_heartbeat, app),
        )

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()
        if app.state.rabbitmq_rpc_server:
            await app.state.rabbitmq_rpc_server.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not app.state.rabbitmq_client:
        raise ConfigurationError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    return cast(RabbitMQClient, app.state.rabbitmq_client)


async def post_message(app: FastAPI, message: RabbitMessageBase) -> None:
    with log_catch(logger, reraise=False), contextlib.suppress(ConfigurationError):
        # NOTE: if rabbitmq was not initialized the error does not need to flood the logs
        await get_rabbitmq_client(app).publish(message.channel_name, message)
