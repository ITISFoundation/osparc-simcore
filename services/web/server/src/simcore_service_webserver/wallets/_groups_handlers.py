""" Handlers for project comments operations

"""

import functools
import logging

from aiohttp import web
from models_library.users import GroupID, UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, Extra, Field
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY
from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _groups_api
from ._groups_api import WalletGroupGet
from ._handlers import WalletsPathParams
from .errors import WalletAccessForbiddenError, WalletGroupNotFoundError

_logger = logging.getLogger(__name__)


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


def _handle_wallets_groups_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except WalletGroupNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except WalletAccessForbiddenError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


#
# wallets groups COLLECTION -------------------------
#

routes = web.RouteTableDef()


class _WalletsGroupsPathParams(BaseModel):
    wallet_id: WalletID
    group_id: GroupID

    class Config:
        extra = Extra.forbid


class _WalletsGroupsBodyParams(BaseModel):
    read: bool
    write: bool
    delete: bool

    class Config:
        extra = Extra.forbid


@routes.post(
    f"/{VTAG}/wallets/{{wallet_id}}/groups/{{group_id}}", name="create_wallet_group"
)
@login_required
@permission_required("wallets.*")
@_handle_wallets_groups_exceptions
async def create_wallet_group(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_WalletsGroupsPathParams, request)
    body_params = await parse_request_body_as(_WalletsGroupsBodyParams, request)

    wallet_groups: WalletGroupGet = await _groups_api.create_wallet_group(
        request.app,
        user_id=req_ctx.user_id,
        wallet_id=path_params.wallet_id,
        group_id=path_params.group_id,
        read=body_params.read,
        write=body_params.write,
        delete=body_params.delete,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(wallet_groups, web.HTTPCreated)


@routes.get(f"/{VTAG}/wallets/{{wallet_id}}/groups", name="list_wallet_groups")
@login_required
@permission_required("wallets.*")
@_handle_wallets_groups_exceptions
async def list_wallet_groups(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WalletsPathParams, request)

    wallets: list[
        WalletGroupGet
    ] = await _groups_api.list_wallet_groups_by_user_and_wallet(
        request.app,
        user_id=req_ctx.user_id,
        wallet_id=path_params.wallet_id,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(wallets, web.HTTPOk)


@routes.put(
    f"/{VTAG}/wallets/{{wallet_id}}/groups/{{group_id}}",
    name="update_wallet_group",
)
@login_required
@permission_required("wallets.*")
@_handle_wallets_groups_exceptions
async def update_wallet_group(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_WalletsGroupsPathParams, request)
    body_params = await parse_request_body_as(_WalletsGroupsBodyParams, request)

    return await _groups_api.update_wallet_group(
        app=request.app,
        user_id=req_ctx.user_id,
        wallet_id=path_params.wallet_id,
        group_id=path_params.group_id,
        read=body_params.read,
        write=body_params.write,
        delete=body_params.delete,
        product_name=req_ctx.product_name,
    )


@routes.delete(
    f"/{VTAG}/wallets/{{wallet_id}}/groups/{{group_id}}",
    name="delete_wallet_group",
)
@login_required
@permission_required("wallets.*")
@_handle_wallets_groups_exceptions
async def delete_wallet_group(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_WalletsGroupsPathParams, request)

    await _groups_api.delete_wallet_group(
        app=request.app,
        user_id=req_ctx.user_id,
        wallet_id=path_params.wallet_id,
        group_id=path_params.group_id,
        product_name=req_ctx.product_name,
    )
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
