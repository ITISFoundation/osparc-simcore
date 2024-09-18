import functools
import logging

from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    CreateWalletBodyParams,
    PutWalletBodyParams,
    WalletGet,
    WalletGetWithAvailableCredits,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import Field
from servicelib.aiohttp.requests_validation import (
    RequestParams,
    StrictRequestParams,
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG as VTAG
from ..application_settings_utils import requires_dev_feature_enabled
from ..login.decorators import login_required
from ..payments.errors import (
    InvalidPaymentMethodError,
    PaymentCompletedError,
    PaymentMethodAlreadyAckedError,
    PaymentMethodNotFoundError,
    PaymentMethodUniqueViolationError,
    PaymentNotFoundError,
    PaymentServiceUnavailableError,
    PaymentUniqueViolationError,
)
from ..products.errors import BelowMinimumPaymentError, ProductPriceNotDefinedError
from ..security.decorators import permission_required
from ..users.exceptions import UserDefaultWalletNotFoundError
from ..utils_aiohttp import envelope_json_response
from . import _api
from ._constants import MSG_PRICE_NOT_DEFINED_ERROR
from .errors import WalletAccessForbiddenError, WalletNotFoundError

_logger = logging.getLogger(__name__)


def handle_wallets_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except (
            WalletNotFoundError,
            PaymentNotFoundError,
            PaymentMethodNotFoundError,
            UserDefaultWalletNotFoundError,
        ) as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except (
            PaymentUniqueViolationError,
            PaymentCompletedError,
            PaymentMethodAlreadyAckedError,
            PaymentMethodUniqueViolationError,
            InvalidPaymentMethodError,
        ) as exc:
            raise web.HTTPConflict(reason=f"{exc}") from exc

        except PaymentServiceUnavailableError as exc:
            raise web.HTTPServiceUnavailable(reason=f"{exc}") from exc

        except WalletAccessForbiddenError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

        except BelowMinimumPaymentError as exc:
            raise web.HTTPUnprocessableEntity(reason=f"{exc}") from exc

        except ProductPriceNotDefinedError as exc:
            raise web.HTTPConflict(reason=MSG_PRICE_NOT_DEFINED_ERROR) from exc

    return wrapper


#
# wallets COLLECTION -------------------------
#

routes = web.RouteTableDef()


class WalletsRequestContext(RequestParams):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


class WalletsPathParams(StrictRequestParams):
    wallet_id: WalletID


@routes.post(f"/{VTAG}/wallets", name="create_wallet")
@requires_dev_feature_enabled  # NOTE: one wallet per user+product. SEE _events.py:_auto_add_default_wallet
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
async def create_wallet(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    body_params = await parse_request_body_as(CreateWalletBodyParams, request)

    wallet: WalletGet = await _api.create_wallet(
        request.app,
        user_id=req_ctx.user_id,
        wallet_name=body_params.name,
        description=body_params.description,
        thumbnail=body_params.thumbnail,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(wallet, web.HTTPCreated)


@routes.get(f"/{VTAG}/wallets", name="list_wallets")
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
async def list_wallets(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)

    wallets: list[
        WalletGetWithAvailableCredits
    ] = await _api.list_wallets_with_available_credits_for_user(
        app=request.app, user_id=req_ctx.user_id, product_name=req_ctx.product_name
    )

    return envelope_json_response(wallets)


@routes.get(f"/{VTAG}/wallets/default", name="get_default_wallet")
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
async def get_default_wallet(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)

    wallet: WalletGetWithAvailableCredits = (
        await _api.get_user_default_wallet_with_available_credits(
            app=request.app, user_id=req_ctx.user_id, product_name=req_ctx.product_name
        )
    )
    return envelope_json_response(wallet)


@routes.get(f"/{VTAG}/wallets/{{wallet_id}}", name="get_wallet")
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
async def get_wallet(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WalletsPathParams, request)

    wallet: WalletGetWithAvailableCredits = (
        await _api.get_wallet_with_available_credits_by_user_and_wallet(
            app=request.app,
            wallet_id=path_params.wallet_id,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
        )
    )

    return envelope_json_response(wallet)


@routes.put(
    f"/{VTAG}/wallets/{{wallet_id}}",
    name="update_wallet",
)
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
async def update_wallet(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WalletsPathParams, request)
    body_params = await parse_request_body_as(PutWalletBodyParams, request)

    updated_wallet: WalletGet = await _api.update_wallet(
        app=request.app,
        user_id=req_ctx.user_id,
        wallet_id=path_params.wallet_id,
        name=body_params.name,
        description=body_params.description,
        thumbnail=body_params.thumbnail,
        status=body_params.status,
        product_name=req_ctx.product_name,
    )
    return envelope_json_response(updated_wallet)
