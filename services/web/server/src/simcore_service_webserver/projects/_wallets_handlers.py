""" Handlers for CRUD operations on /projects/{*}/wallet

"""

import functools
import logging
from decimal import Decimal

from aiohttp import web
from models_library.api_schemas_webserver.wallets import WalletGet
from models_library.projects import ProjectID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from simcore_service_webserver.utils_aiohttp import envelope_json_response

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..wallets.errors import WalletAccessForbiddenError
from . import _wallets_api as wallets_api
from . import projects_api
from ._common.models import ProjectPathParams, RequestContext
from .exceptions import ProjectInvalidRightsError, ProjectNotFoundError

_logger = logging.getLogger(__name__)


def _handle_project_wallet_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except ProjectNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except (WalletAccessForbiddenError, ProjectInvalidRightsError) as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/projects/{{project_id}}/wallet", name="get_project_wallet")
@login_required
@permission_required("project.wallet.*")
@_handle_project_wallet_exceptions
async def get_project_wallet(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
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
    model_config = ConfigDict(extra="forbid")


@routes.put(
    f"/{API_VTAG}/projects/{{project_id}}/wallet/{{wallet_id}}",
    name="connect_wallet_to_project",
)
@login_required
@permission_required("project.wallet.*")
@_handle_project_wallet_exceptions
async def connect_wallet_to_project(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_ProjectWalletPathParams, request)

    # ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    wallet: WalletGet = await wallets_api.connect_wallet_to_project(
        request.app,
        product_name=req_ctx.product_name,
        project_id=path_params.project_id,
        user_id=req_ctx.user_id,
        wallet_id=path_params.wallet_id,
    )

    return envelope_json_response(wallet)


class _PayProjectDebtBody(BaseModel):
    amount: Decimal
    model_config = ConfigDict(extra="forbid")


@routes.post(
    f"/{API_VTAG}/projects/{{project_id}}/wallet/{{wallet_id}}:pay-debt",
    name="pay_project_debt",
)
@login_required
@permission_required("project.wallet.*")
@_handle_project_wallet_exceptions
async def pay_project_debt(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_ProjectWalletPathParams, request)
    body_params = await parse_request_body_as(_PayProjectDebtBody, request)

    # Ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    # Ensure the wallet is associated with the project
    wallet: WalletGet | None = await wallets_api.get_project_wallet(
        request.app, path_params.project_id
    )
    if not wallet:
        raise web.HTTPNotFound(reason="Wallet not associated with the project")

    if wallet.wallet_id == path_params.wallet_id:
        # NOTE: Currently, this option is not supported. The only way a user can
        # access their project with the same wallet is by topping it up to achieve
        # a positive balance. (This could potentially be improved in the future;
        # for example, we might allow users to top up credits specifically for the
        # debt of a particular project, which would unblock access to that project.)
        # At present, once the wallet balance becomes positive, RUT updates all
        # projects connected to that wallet from IN_DEBT to BILLED.

        web.json_response(status=status.HTTP_501_NOT_IMPLEMENTED)
    else:
        # The debt is being paid using a different wallet than the one currently connected to the project.
        # Steps:
        # 1. Transfer the required credits from the specified wallet to the connected wallet.
        # 2. Mark the transaction as billed (This will allow to )

        await wallets_api.pay_debt_with_different_wallet(
            app=request.app,
            product_name=req_ctx.product_name,
            project_id=path_params.project_id,
            user_id=req_ctx.user_id,
            current_wallet_id=wallet.wallet_id,
            new_wallet_id=path_params.wallet_id,
            debt_amount=body_params.amount,
        )

    return envelope_json_response(payment_result)
