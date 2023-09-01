import asyncio
import logging
import random
from typing import Any

from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    CreateWalletPayment,
    PaymentTransaction,
    WalletGet,
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
from servicelib.utils import fire_and_forget_task

from .._constants import APP_FIRE_AND_FORGET_TASKS_KEY
from .._meta import API_VTAG as VTAG
from ..application_settings import get_settings
from ..login.decorators import login_required
from ..payments._api import complete_payment
from ..payments.api import create_payment_to_wallet, get_user_payments_page
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from ._handlers import (
    WalletsPathParams,
    WalletsRequestContext,
    handle_wallets_exceptions,
)
from .api import get_wallet_by_user

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


def _raise_if_not_dev_mode(app):
    app_settings = get_settings(app)
    if not app_settings.WEBSERVER_DEV_FEATURES_ENABLED:
        msg = "This feature is only available in development mode"
        raise NotImplementedError(msg)


async def _fake_payment_completion(app: web.Application, payment: WalletPaymentCreated):
    # Fakes processing time
    processing_time = random.uniform(0.5, 2)  # noqa: S311
    await asyncio.sleep(processing_time)

    # Three different possible outcomes
    possible_outcomes = [
        # 1. Accepted
        {"app": app, "payment_id": payment.payment_id, "success": True},
        # 2. Rejected
        {
            "app": app,
            "payment_id": payment.payment_id,
            "success": False,
            "error_msg": "Payment rejected",
        },
        # TODO: 3. does not complete ever
    ]
    kwargs: dict[str, Any] = random.choice(possible_outcomes)  # noqa: S311
    await complete_payment(**kwargs)


@routes.post(f"/{VTAG}/wallets/{{wallet_id}}/payments", name="create_payment")
@login_required
@permission_required("wallets.*")
@handle_wallets_exceptions
async def create_payment(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WalletsPathParams, request)
    body_params = await parse_request_body_as(CreateWalletPayment, request)

    _raise_if_not_dev_mode(request.app)

    # ensure the wallet can be used by the user
    wallet: WalletGet = await get_wallet_by_user(
        request.app,
        user_id=req_ctx.user_id,
        wallet_id=path_params.wallet_id,
        has_write_permission=True,  # Can only pay to wallets that user owns
    )
    wallet_id = wallet.wallet_id

    with log_context(
        _logger,
        logging.INFO,
        "Payment transaction started to %s",
        f"{wallet_id=}",
        log_duration=True,
        extra=get_log_record_extra(user_id=req_ctx.user_id),
    ):
        payment = await create_payment_to_wallet(
            request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
            wallet_id=wallet.wallet_id,
            wallet_name=wallet.name,
            osparc_credit=body_params.osparc_credits,
            price_dollars=body_params.price_dollars,
            comment=body_params.comment,
        )

    # NOTE: fake completion for the moment
    await fire_and_forget_task(
        _fake_payment_completion(request.app, payment),
        task_suffix_name=f"fake_payment_completion_{payment.payment_id}",
        fire_and_forget_tasks_collection=request.app[APP_FIRE_AND_FORGET_TASKS_KEY],
    )

    return envelope_json_response(
        WalletPaymentCreated.parse_obj(payment), web.HTTPCreated
    )


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
