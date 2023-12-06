from aiohttp import web
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID

from . import _rpc


async def get_dynamic_service(
    app: web.Application, *, node_id: NodeID
) -> NodeGetIdle | DynamicServiceGet | NodeGet:
    return await _rpc.get_service_status(app, node_id=node_id)
