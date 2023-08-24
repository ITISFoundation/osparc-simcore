from fastapi import FastAPI
from simcore_service_clusters_keeper.modules.rabbitmq import get_rabbitmq_rpc_client

from .._meta import RPC_VTAG
from . import clusters


def setup_rpc_routes(app: FastAPI) -> None:
    async def on_startup(app: FastAPI) -> None:
        rpc_client = get_rabbitmq_rpc_client(app)
        await rpc_client.rpc_register_handler(
            CLUSTERS_KEEPER_RPC_NAMESPACE,
            RPCMethodName("create_cluster"),
            functools.partial(create_cluster, app),
        )

        await rpc_client.rpc_register_handler(
            CLUSTERS_KEEPER_RPC_NAMESPACE,
            RPCMethodName("cluster_heartbeat"),
            functools.partial(cluster_heartbeat, app),
        )

        router = RPCRouter()

        # include operations in /
        app.include_router(clusters.router, tags=["operations"])

        # include the rest under /vX
        app.include_router(router, prefix=f"/{RPC_VTAG}")

    async def on_shutdown(app: FastAPI) -> None:
        ...

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
