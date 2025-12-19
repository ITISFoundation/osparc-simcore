import logging

from aiohttp import web
from models_library.api_schemas_webserver.licensed_items_checkouts import (
    LicensedItemCheckoutRestGet,
    LicensedItemCheckoutRestGetPage,
)
from models_library.rest_ordering import OrderBy
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from ..wallets._handlers import WalletsPathParams
from . import _licensed_items_checkouts_service
from ._common.exceptions_handlers import handle_plugin_requests_exceptions
from ._common.models import LicensedItemsRequestContext
from ._licensed_items_checkouts_models import (
    LicensedItemCheckoutGet,
    LicensedItemCheckoutGetPage,
    LicensedItemCheckoutPathParams,
    LicensedItemsCheckoutsListQueryParams,
)

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.get(
    f"/{VTAG}/licensed-items-checkouts/{{licensed_item_checkout_id}}",
    name="get_licensed_item_checkout",
)
@login_required
@permission_required("catalog/licensed-items.*")
@handle_plugin_requests_exceptions
async def get_licensed_item_checkout(request: web.Request):
    req_ctx = LicensedItemsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        LicensedItemCheckoutPathParams, request
    )

    checkout_item: LicensedItemCheckoutGet = (
        await _licensed_items_checkouts_service.get_licensed_item_checkout(
            app=request.app,
            product_name=req_ctx.product_name,
            user_id=req_ctx.user_id,
            licensed_item_checkout_id=path_params.licensed_item_checkout_id,
        )
    )

    output = LicensedItemCheckoutRestGet.model_construct(
        licensed_item_checkout_id=checkout_item.licensed_item_checkout_id,
        licensed_item_id=checkout_item.licensed_item_id,
        key=checkout_item.key,
        version=checkout_item.version,
        wallet_id=checkout_item.wallet_id,
        user_id=checkout_item.user_id,
        user_email=checkout_item.user_email,
        product_name=checkout_item.product_name,
        started_at=checkout_item.started_at,
        stopped_at=checkout_item.stopped_at,
        num_of_seats=checkout_item.num_of_seats,
    )

    return envelope_json_response(output)


@routes.get(
    f"/{VTAG}/wallets/{{wallet_id}}/licensed-items-checkouts",
    name="list_licensed_item_checkouts_for_wallet",
)
@login_required
@permission_required("catalog/licensed-items.*")
@handle_plugin_requests_exceptions
async def list_licensed_item_checkouts_for_wallet(request: web.Request):
    req_ctx = LicensedItemsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(WalletsPathParams, request)
    query_params: LicensedItemsCheckoutsListQueryParams = (
        parse_request_query_parameters_as(
            LicensedItemsCheckoutsListQueryParams, request
        )
    )

    result: LicensedItemCheckoutGetPage = await _licensed_items_checkouts_service.list_licensed_items_checkouts_for_wallet(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        wallet_id=path_params.wallet_id,
        offset=query_params.offset,
        limit=query_params.limit,
        order_by=OrderBy.model_construct(**query_params.order_by.model_dump()),
    )

    get_page = LicensedItemCheckoutRestGetPage(
        total=result.total,
        items=[
            LicensedItemCheckoutRestGet.model_construct(
                licensed_item_checkout_id=checkout_item.licensed_item_checkout_id,
                licensed_item_id=checkout_item.licensed_item_id,
                key=checkout_item.key,
                version=checkout_item.version,
                wallet_id=checkout_item.wallet_id,
                user_id=checkout_item.user_id,
                user_email=checkout_item.user_email,
                product_name=checkout_item.product_name,
                started_at=checkout_item.started_at,
                stopped_at=checkout_item.stopped_at,
                num_of_seats=checkout_item.num_of_seats,
            )
            for checkout_item in result.items
        ],
    )

    page = Page[LicensedItemCheckoutRestGet].model_validate(
        paginate_data(
            chunk=get_page.items,
            request_url=request.url,
            total=get_page.total,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )
