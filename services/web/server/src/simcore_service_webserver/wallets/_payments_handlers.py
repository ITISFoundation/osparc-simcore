import logging

from aiohttp import web
from models_library.api_schemas_webserver._base import OutputSchema
from models_library.api_schemas_webserver.wallets import PaymentGet
from models_library.rest_pagination import Page, PageQueryParameters
from models_library.rest_pagination_utils import paginate_data
from pydantic import PositiveFloat
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..payments.api import create_payment_to_wallet, get_user_payments_page
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from ._handlers import WalletsPathParams, WalletsRequestContext

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


class PaymentCreateBody(OutputSchema):
    prize: PositiveFloat
    credit: PositiveFloat  # NOTE: should I recompute? or should be in the backend?


@routes.post(f"/{VTAG}/wallets/{{wallet_id}}/payments", name="create_payment")
@login_required
@permission_required("wallets.*")
async def create_payment(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WalletsPathParams, request)
    body_params = await parse_request_body_as(PaymentCreateBody, request)

    payment = await create_payment_to_wallet(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        wallet_id=path_params.wallet_id,
        credit=body_params.credit,
        prize=body_params.prize,
    )
    return envelope_json_response(PaymentGet.parse_obj(payment), web.HTTPCreated)


@routes.post(f"/{VTAG}/wallets/-/payments", name="list_all_wallets_payments")
@login_required
@permission_required("wallets.*")
async def list_all_payments(request: web.Request):
    req_ctx = WalletsRequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(PageQueryParameters, request)

    payments, total_number_of_items = await get_user_payments_page(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        limit=query_params.limit,
        offset=query_params.offset,
    )

    page = Page[PaymentGet].parse_obj(
        paginate_data(
            chunk=payments,
            request_url=request.url,
            total=total_number_of_items,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )

    return envelope_json_response(page, web.HTTPOk)
