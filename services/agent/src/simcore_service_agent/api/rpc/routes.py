from fastapi import FastAPI
from models_library.rabbitmq_basic_types import RPCNamespace
from servicelib.rabbitmq import RPCRouter
from simcore_service_agent.core.settings import ApplicationSettings

from ...services.rabbitmq import get_rabbitmq_rpc_server
from . import _containers, _volumes

ROUTERS: list[RPCRouter] = [
    _containers.router,
    _volumes.router,
]


def setup_rpc_api_routes(app: FastAPI) -> None:
    async def startup() -> None:
        rpc_server = get_rabbitmq_rpc_server(app)
        settings: ApplicationSettings = app.state.settings
        rpc_namespace = RPCNamespace.from_entries(
            {
                "service": "agent",
                "docker_node_id": settings.AGENT_DOCKER_NODE_ID,
                "swarm_stack_name": settings.AGENT_VOLUMES_CLEANUP_TARGET_SWARM_STACK_NAME,
            }
        )
        for router in ROUTERS:
            await rpc_server.register_router(router, rpc_namespace, app)

        await rpc_server.start()

    app.add_event_handler("startup", startup)


# TODO: figure out how to merge the inerfaces, since now the RPC servicer registration needs to be done before starting the servcer and this one
