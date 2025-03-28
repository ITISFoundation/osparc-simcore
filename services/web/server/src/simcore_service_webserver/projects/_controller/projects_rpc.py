from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import ValidationError, validate_call
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.webserver.errors import (
    ProjectForbiddenRpcError,
    ProjectNotFoundRpcError,
)

from ...rabbitmq import get_rabbitmq_rpc_server
from .. import _jobs_service
from ..exceptions import ProjectInvalidRightsError

router = RPCRouter()


@router.expose(
    reraise_if_error_type=(
        ProjectForbiddenRpcError,
        ProjectNotFoundRpcError,
        ValidationError,
    )
)
@validate_call(config={"arbitrary_types_allowed": True})
async def mark_project_as_job(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    job_parent_resource_name: str,
) -> None:

    try:

        await _jobs_service.set_project_as_job(
            app,
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
            job_parent_resource_name=job_parent_resource_name,
        )
    except ProjectInvalidRightsError as err:
        raise ProjectForbiddenRpcError.from_domain_error(err) from err


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
