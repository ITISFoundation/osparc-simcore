import logging

from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    CreateWalletPayment,
    PaymentID,
    PaymentTransaction,
    WalletPaymentCreated,
)
from models_library.rest_pagination import Page, PageQueryParameters
from models_library.rest_pagination_utils import paginate_data
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.logging_utils import get_log_record_extra, log_context

from .._meta import API_VTAG as VTAG
from ..application_settings import get_settings
from ..login.decorators import login_required
from ..payments import api
from ..payments.api import create_payment_to_wallet, get_user_payments_page
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from ._handlers import (
    WalletsPathParams,
    WalletsRequestContext,
    handle_wallets_exceptions,
)

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


def _raise_if_not_dev_mode(app):
    app_settings = get_settings(app)
    if not app_settings.WEBSERVER_DEV_FEATURES_ENABLED:
        msg = "This feature is only available in development mode"
        raise NotImplementedError(msg)


@routes.post(f"/{VTAG}/wallets/{{wallet_id}}/payments", name="create_payment")
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
async def create_payment(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WalletsPathParams, request)
    body_params = await parse_request_body_as(CreateWalletPayment, request)

    _raise_if_not_dev_mode(request.app)

    wallet_id = path_params.wallet_id

    with log_context(
        _logger,
        logging.INFO,
        "Payment transaction started to %s",
        f"{wallet_id=}",
        log_duration=True,
        extra=get_log_record_extra(user_id=req_ctx.user_id),
    ):
        payment: WalletPaymentCreated = await create_payment_to_wallet(
            request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
            wallet_id=wallet_id,
            osparc_credit=body_params.osparc_credits,
            price_dollars=body_params.price_dollars,
            comment=body_params.comment,
        )

    return envelope_json_response(payment, web.HTTPCreated)


@routes.get(f"/{VTAG}/wallets/-/payments", name="list_all_payments")
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
async def list_all_payments(request: web.Request):
    """Lists all user's payments to any of his wallets

    NOTE that only payments attributed to this user will be listed here
    e.g. if another user did some payments to a shared wallet, it will not
    be listed here.
    """

    req_ctx = WalletsRequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(PageQueryParameters, request)

    _raise_if_not_dev_mode(request.app)

    payments, total_number_of_items = await get_user_payments_page(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        limit=query_params.limit,
        offset=query_params.offset,
    )

    page = Page[PaymentTransaction].parse_obj(
        paginate_data(
            chunk=payments,
            request_url=request.url,
            total=total_number_of_items,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )

    return envelope_json_response(page, web.HTTPOk)


class PaymentsPathParams(WalletsPathParams):
    payment_id: PaymentID


@routes.post(
    f"/{VTAG}/wallets/{{wallet_id}}/payments/{{payment_id}}", name="cancel_payment"
)
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
async def cancel_payment(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(PaymentsPathParams, request)

    _raise_if_not_dev_mode(request.app)

    await api.cancel_payment_to_wallet(
        request.app,
        user_id=req_ctx.user_id,
        wallet_id=path_params.wallet_id,
        payment_id=path_params.payment_id,
    )

    return web.HTTPNoContent()
