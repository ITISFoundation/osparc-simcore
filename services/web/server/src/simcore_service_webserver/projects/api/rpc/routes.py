from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.projects import ProjectID
from models_library.projects_nodes import Node
from models_library.rpc.webserver.projects.projects_nodes import ProjectNodeGet
from pydantic import TypeAdapter
from servicelib.rabbitmq import RPCRouter

from ....rabbitmq import get_rabbitmq_rpc_server
from ... import projects_service

router = RPCRouter()


@router.expose()
async def list_project_nodes(
    app: web.Application,
    *,
    project_uuid: ProjectID,
) -> list[ProjectNodeGet]:
    nodes: list[Node] = await projects_service.list_project_nodes(app, project_uuid)
    return TypeAdapter(list[ProjectNodeGet]).validate_python(nodes)


async def register_rpc_routes(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
