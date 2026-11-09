from aiohttp import web
from models_library.api_schemas_webserver.projects_metadata import MetadataDict
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import ValidationError, validate_call
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.webserver.errors import (
    ProjectForbiddenRpcError,
    ProjectNotFoundRpcError,
)

from ...application_settings import get_application_settings
from ...rabbitmq import get_rabbitmq_rpc_client
from .. import _metadata_service
from ..exceptions import ProjectInvalidRightsError, ProjectNotFoundError

router = RPCRouter()


@router.expose(
    reraise_if_error_type=(
        ProjectForbiddenRpcError,
        ProjectNotFoundRpcError,
        ValidationError,
    )
)
@validate_call(config={"arbitrary_types_allowed": True})
async def batch_get_project_custom_metadata(
    app: web.Application,
    *,
    product_name: ProductName,  # noqa: ARG001 # pylint: disable=unused-argument
    user_id: UserID,
    project_uuids: list[ProjectID],
) -> dict[ProjectID, MetadataDict]:
    try:
        return await _metadata_service.batch_get_project_custom_metadata_for_user(
            app, user_id=user_id, project_uuids=project_uuids
        )
    except ProjectInvalidRightsError as err:
        raise ProjectForbiddenRpcError.from_domain_error(err) from err
    except ProjectNotFoundError as err:
        raise ProjectNotFoundRpcError.from_domain_error(err) from err


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_client = get_rabbitmq_rpc_client(app)
    settings = get_application_settings(app)
    if not settings.WEBSERVER_RPC_NAMESPACE:
        msg = "RPC namespace is not configured"
        raise ValueError(msg)

    await rpc_client.register_router(router, settings.WEBSERVER_RPC_NAMESPACE, app)
