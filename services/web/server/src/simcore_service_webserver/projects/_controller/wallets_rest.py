import logging
from decimal import Decimal
from typing import Annotated

from aiohttp import web
from models_library.api_schemas_webserver.wallets import WalletGet
from models_library.projects import ProjectID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict, Field
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)

from ..._meta import API_VTAG
from ...login.decorators import login_required
from ...security.decorators import permission_required
from ...utils_aiohttp import envelope_json_response
from .. import _projects_service, _wallets_service
from ._rest_exceptions import handle_plugin_requests_exceptions
from ._rest_schemas import AuthenticatedRequestContext, ProjectPathParams

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/projects/{{project_id}}/wallet", name="get_project_wallet")
@login_required
@permission_required("project.wallet.*")
@handle_plugin_requests_exceptions
async def get_project_wallet(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=False,
    )
    wallet: WalletGet | None = await _wallets_service.get_project_wallet(
        request.app, path_params.project_id
    )

    return envelope_json_response(wallet)


class _ProjectWalletPathParams(BaseModel):
    project_id: ProjectID
    wallet_id: WalletID
    model_config = ConfigDict(extra="forbid")


@routes.put(
    f"/{API_VTAG}/projects/{{project_id}}/wallet/{{wallet_id}}",
    name="connect_wallet_to_project",
)
@login_required
@permission_required("project.wallet.*")
@handle_plugin_requests_exceptions
async def connect_wallet_to_project(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_ProjectWalletPathParams, request)

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    wallet: WalletGet = await _wallets_service.connect_wallet_to_project(
        request.app,
        product_name=req_ctx.product_name,
        project_id=path_params.project_id,
        user_id=req_ctx.user_id,
        wallet_id=path_params.wallet_id,
    )

    return envelope_json_response(wallet)


class _PayProjectDebtBody(BaseModel):
    amount: Annotated[Decimal, Field(lt=0)]
    model_config = ConfigDict(extra="forbid")


@routes.post(
    f"/{API_VTAG}/projects/{{project_id}}/wallet/{{wallet_id}}:pay-debt",
    name="pay_project_debt",
)
@login_required
@permission_required("project.wallet.*")
@handle_plugin_requests_exceptions
async def pay_project_debt(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_ProjectWalletPathParams, request)
    body_params = await parse_request_body_as(_PayProjectDebtBody, request)

    # Ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    # Get curently associated wallet with the project
    current_wallet: WalletGet | None = await _wallets_service.get_project_wallet(
        request.app, path_params.project_id
    )
    if not current_wallet:
        raise web.HTTPNotFound(
            reason="Project doesn't have any wallet associated to the project"
        )

    if current_wallet.wallet_id == path_params.wallet_id:
        # NOTE: Currently, this option is not supported. The only way a user can
        # access their project with the same wallet is by topping it up to achieve
        # a positive balance. (This could potentially be improved in the future;
        # for example, we might allow users to top up credits specifically for the
        # debt of a particular project, which would unblock access to that project.)
        # At present, once the wallet balance becomes positive, RUT updates all
        # projects connected to that wallet from IN_DEBT to BILLED.

        raise web.HTTPNotImplemented

    # The debt is being paid using a different wallet than the one currently connected to the project.
    # Steps:
    # 1. Transfer the required credits from the specified wallet to the connected wallet.
    # 2. Mark the project transactions as billed
    await _wallets_service.pay_debt_with_different_wallet(
        app=request.app,
        product_name=req_ctx.product_name,
        project_id=path_params.project_id,
        user_id=req_ctx.user_id,
        current_wallet_id=current_wallet.wallet_id,
        new_wallet_id=path_params.wallet_id,
        debt_amount=body_params.amount,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
