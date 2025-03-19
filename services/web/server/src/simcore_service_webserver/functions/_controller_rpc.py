from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from servicelib.rabbitmq import RPCRouter
from simcore_service_webserver.rabbitmq import get_rabbitmq_rpc_server

# this is the rpc interface exposed to the api-server
# this interface should call the service layer

router = RPCRouter()


@router.expose()
async def ping(app) -> str:
    return "pong"


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
