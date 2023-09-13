import functools
import logging

from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    CreateWalletPayment,
    PaymentID,
    PaymentMethodCreated,
    PaymentMethodGet,
    PaymentTransaction,
    WalletPaymentCreated,
)
from models_library.rest_pagination import Page, PageQueryParameters
from models_library.rest_pagination_utils import paginate_data
from pydantic import parse_obj_as
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from .._constants import MSG_UNDER_DEVELOPMENT
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


def raise_if_not_dev_feature_enabled(handler: Handler):
    @functools.wraps(handler)
    async def _handler_under_dev(request: web.Request):
        app_settings = get_settings(request.app)
        if not app_settings.WEBSERVER_DEV_FEATURES_ENABLED:
            raise NotImplementedError(MSG_UNDER_DEVELOPMENT)
        return await handler(request)

    return _handler_under_dev


@routes.post(f"/{VTAG}/wallets/{{wallet_id}}/payments", name="create_payment")
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
@raise_if_not_dev_feature_enabled
async def create_payment(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WalletsPathParams, request)
    body_params = await parse_request_body_as(CreateWalletPayment, request)

    wallet_id = path_params.wallet_id

    with log_context(
        _logger,
        logging.INFO,
        "Payment transaction started to %s",
        f"{wallet_id=}",
        log_duration=True,
        extra=get_log_record_extra(user_id=req_ctx.user_id),
    ):
        # WARNING: conversion here is 1 dollar = 1 credit. Follow up logic discussed in https://github.com/ITISFoundation/osparc-simcore/issues/4657
        osparc_credits = body_params.price_dollars

        payment: WalletPaymentCreated = await create_payment_to_wallet(
            request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
            wallet_id=wallet_id,
            osparc_credits=osparc_credits,
            comment=body_params.comment,
            price_dollars=body_params.price_dollars,
        )

    return envelope_json_response(payment, web.HTTPCreated)


@routes.get(f"/{VTAG}/wallets/-/payments", name="list_all_payments")
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
@raise_if_not_dev_feature_enabled
async def list_all_payments(request: web.Request):
    """Lists all user's payments to any of his wallets

    NOTE that only payments attributed to this user will be listed here
    e.g. if another user did some payments to a shared wallet, it will not
    be listed here.
    """

    req_ctx = WalletsRequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(PageQueryParameters, request)

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
    f"/{VTAG}/wallets/{{wallet_id}}/payments/{{payment_id}}:cancel",
    name="cancel_payment",
)
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
@raise_if_not_dev_feature_enabled
async def cancel_payment(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(PaymentsPathParams, request)

    await api.cancel_payment_to_wallet(
        request.app,
        user_id=req_ctx.user_id,
        wallet_id=path_params.wallet_id,
        payment_id=path_params.payment_id,
    )

    return web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


class PaymentMethodsPathParams(WalletsPathParams):
    payment_method_id: PaymentID


@routes.post(
    f"/{VTAG}/wallets/{{wallet_id}}/payments-methods", name="create_payment_method"
)
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
@raise_if_not_dev_feature_enabled
async def create_payment_method(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WalletsPathParams, request)

    created = parse_obj_as(
        PaymentMethodCreated,
        {
            **PaymentMethodCreated.Config.schema_extra["examples"][0],
            "wallet_id": path_params.wallet_id,
        },
    )
    return envelope_json_response(created)


@routes.get(
    f"/{VTAG}/wallets/{{wallet_id}}/payments-methods", name="list_payment_methods"
)
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
@raise_if_not_dev_feature_enabled
async def list_payment_methods(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WalletsPathParams, request)
    payment_methods = parse_obj_as(
        list[PaymentMethodGet],
        [
            {**p, "wallet_id": path_params.wallet_id}
            for p in PaymentMethodGet.Config.schema_extra["examples"]
        ],
    )
    return envelope_json_response(payment_methods)


@routes.get(
    f"/{VTAG}/wallets/{{wallet_id}}/payments-methods/{{payment_method_id}}",
    name="get_payment_method",
)
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
@raise_if_not_dev_feature_enabled
async def get_payment_method(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(PaymentMethodsPathParams, request)

    got = parse_obj_as(
        PaymentMethodGet,
        {
            **PaymentMethodGet.Config.schema_extra["examples"][0],
            "idr": path_params.payment_method_id,
            "wallet_id": path_params.wallet_id,
        },
    )
    return envelope_json_response(got)


@routes.delete(
    f"/{VTAG}/wallets/{{wallet_id}}/payments-methods/{{payment_method_id}}",
    name="delete_payment_method",
)
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
@raise_if_not_dev_feature_enabled
async def delete_payment_method(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(PaymentMethodsPathParams, request)

    raise NotImplementedError
