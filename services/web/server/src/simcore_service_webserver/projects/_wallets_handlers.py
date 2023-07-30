""" Handlers for CRUD operations on /projects/{*}/wallet

"""

import logging

from aiohttp import web
from models_library.projects import ProjectID
from models_library.wallets import WalletGet, WalletGetDB, WalletID
from pydantic import BaseModel, Extra
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..wallets import _api as wallet_api
from . import projects_api
from ._common_models import ProjectPathParams, RequestContext
from .db import ProjectDBAPI

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/projects/{{project_id}}/wallet", name="get_project_wallet")
@login_required
# @permission_required("project.tag.*")
async def get_project_wallet(request: web.Request):
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(request.app)
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    # ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    wallet_db: WalletGetDB | None = await db.get_project_wallet(
        project_uuid=path_params.project_id
    )
    output: WalletGet | None = (
        WalletGet(**wallet_db.model_dump()) if wallet_db else None
    )
    return output


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
# @permission_required("project.tag.*")
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
    wallet: WalletGet = await wallet_api.can_wallet_be_used_by_user(
        request.app, user_id=req_ctx.user_id, wallet_id=path_params.wallet_id
    )

    await db.connect_wallet_to_project(
        project_uuid=path_params.project_id, wallet_id=path_params.wallet_id
    )

    return wallet
