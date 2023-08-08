""" Handlers for project comments operations

"""

import functools
import logging

from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    WalletGet,
    WalletGetWithAvailableCredits,
)
from models_library.users import UserID
from models_library.wallets import WalletID, WalletStatus
from pydantic import BaseModel, Extra, Field
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY
from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _api
from .errors import WalletAccessForbiddenError, WalletNotFoundError

_logger = logging.getLogger(__name__)


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[pydantic-alias]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[pydantic-alias]


def _handle_wallets_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except WalletNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except WalletAccessForbiddenError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


#
# wallets COLLECTION -------------------------
#

routes = web.RouteTableDef()


class WalletsPathParams(BaseModel):
    wallet_id: WalletID

    class Config:
        extra = Extra.forbid


class _CreateWalletBodyParams(BaseModel):
    name: str
    description: str | None = None
    thumbnail: str | None = None

    class Config:
        extra = Extra.forbid


@routes.post(f"/{VTAG}/wallets", name="create_wallet")
@login_required
@permission_required("wallets.*")
@_handle_wallets_exceptions
async def create_wallet(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    body_params = await parse_request_body_as(_CreateWalletBodyParams, request)

    wallet: WalletGet = await _api.create_wallet(
        request.app,
        user_id=req_ctx.user_id,
        wallet_name=body_params.name,
        description=body_params.description,
        thumbnail=body_params.thumbnail,
    )

    return envelope_json_response(wallet, web.HTTPCreated)


@routes.get(f"/{VTAG}/wallets", name="list_wallets")
@login_required
@permission_required("wallets.*")
@_handle_wallets_exceptions
async def list_wallets(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)

    wallets: list[
        WalletGetWithAvailableCredits
    ] = await _api.list_wallets_with_available_credits_for_user(
        request.app, user_id=req_ctx.user_id
    )

    return envelope_json_response(wallets, web.HTTPOk)


class _PutWalletBodyParams(BaseModel):
    name: str
    description: str
    thumbnail: str
    status: WalletStatus

    class Config:
        extra = Extra.forbid


@routes.put(
    f"/{VTAG}/wallets/{{wallet_id}}",
    name="update_wallet",
)
@login_required
@permission_required("wallets.*")
@_handle_wallets_exceptions
async def update_wallet(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WalletsPathParams, request)
    body_params = await parse_request_body_as(_PutWalletBodyParams, request)

    return await _api.update_wallet(
        app=request.app,
        user_id=req_ctx.user_id,
        wallet_id=path_params.wallet_id,
        name=body_params.name,
        description=body_params.description,
        thumbnail=body_params.thumbnail,
        status=body_params.status,
    )
