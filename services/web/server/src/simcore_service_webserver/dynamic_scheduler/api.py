from aiohttp import web
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.projects_nodes_io import NodeID

from . import _rpc


async def get_service_status(
    app: web.Application, *, node_id: NodeID
) -> DynamicServiceGet:
    return await _rpc.get_service_status(app, node_id=node_id)
