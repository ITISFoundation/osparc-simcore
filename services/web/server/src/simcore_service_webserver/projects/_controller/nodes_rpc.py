from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import validate_call
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.webserver.errors import (
    NodeNotFoundRpcError,
)
from simcore_postgres_database.utils_projects_nodes import ProjectNodesNodeNotFoundError

from ...application_settings import get_application_settings
from ...rabbitmq import get_rabbitmq_rpc_client
from .. import _nodes_service

router = RPCRouter()


@router.expose(reraise_if_error_type=(NodeNotFoundRpcError,))
@validate_call(config={"arbitrary_types_allowed": True})
async def get_node_service_key_version(
    app: web.Application, *, project_id: ProjectID, node_id: NodeID
) -> tuple[ServiceKey, ServiceVersion]:
    try:
        return await _nodes_service.get_node_service_key_version(app, project_id=project_id, node_id=node_id)
    except ProjectNodesNodeNotFoundError as err:
        raise NodeNotFoundRpcError.from_domain_error(err) from err


async def register_rpc_routes_on_startup(app: web.Application) -> None:
    rpc_client = get_rabbitmq_rpc_client(app)
    settings = get_application_settings(app)
    if not settings.WEBSERVER_RPC_NAMESPACE:
        msg = "RPC namespace is not configured"
        raise ValueError(msg)

    await rpc_client.register_router(router, settings.WEBSERVER_RPC_NAMESPACE, app)
