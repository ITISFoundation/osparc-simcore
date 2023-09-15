""" Handlers for CRUD operations on /projects/{*}/wallet

"""

import functools
import logging

import _wallets_api as wallets_api
from aiohttp import web
from models_library.api_schemas_webserver.wallets import WalletGet
from models_library.projects import ProjectID
from models_library.wallets import WalletID
from pydantic import BaseModel, Extra
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as
from servicelib.aiohttp.typing_extension import Handler
from simcore_service_webserver.utils_aiohttp import envelope_json_response

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..wallets import _api as wallet_api
from ..wallets.errors import WalletAccessForbiddenError
from . import projects_api
from ._common_models import ProjectPathParams, RequestContext
from .db import ProjectDBAPI
from .exceptions import ProjectNotFoundError

_logger = logging.getLogger(__name__)


def _handle_project_wallet_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except ProjectNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except WalletAccessForbiddenError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/projects/{{project_id}}/wallet", name="get_project_wallet")
@login_required
@permission_required("project.wallet.*")
@_handle_project_wallet_exceptions
async def get_project_wallet(request: web.Request):
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    # ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=False,
    )
    wallet: WalletGet | None = await wallets_api.get_project_wallet(
        request.app, path_params.project_id
    )

    return envelope_json_response(wallet)


class _ProjectWalletPathParams(BaseModel):
    project_id: ProjectID
    wallet_id: WalletID

    class Config:
        extra = Extra.forbid


@routes.put(
    f"/{API_VTAG}/projects/{{project_id}}/wallet/{{wallet_id}}",
    name="connect_wallet_to_project",
)
@login_required
@permission_required("project.wallet.*")
@_handle_project_wallet_exceptions
async def connect_wallet_to_project(request: web.Request):
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(request.app)
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_ProjectWalletPathParams, request)

    # ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=False,
    )
    # ensure the wallet can be used by the user
    wallet: WalletGet = await wallet_api.get_wallet_by_user(
        request.app, user_id=req_ctx.user_id, wallet_id=path_params.wallet_id
    )

    await db.connect_wallet_to_project(
        project_uuid=path_params.project_id, wallet_id=path_params.wallet_id
    )

    return envelope_json_response(wallet)
