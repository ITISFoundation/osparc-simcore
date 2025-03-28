from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import validate_call
from servicelib.rabbitmq import RPCRouter

from ...rabbitmq import get_rabbitmq_rpc_server

router = RPCRouter()


@router.expose()
@validate_call(config={"arbitrary_types_allowed": True})
async def mark_project_as_job(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    job_parent_resource_name: str,
) -> None:
    msg = (
        f"You have reached {__name__} but this feature is still not implemented. "
        f"Inputs: {app=}, {product_name=}, {user_id=}, {project_uuid=}, {job_parent_resource_name=}"
    )
    raise NotImplementedError(msg)


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
