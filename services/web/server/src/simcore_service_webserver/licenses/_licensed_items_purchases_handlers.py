import logging

from aiohttp import web
from models_library.api_schemas_webserver.licensed_items_purchases import (
    LicensedItemPurchaseGet,
    LicensedItemPurchaseGetPage,
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
from . import _licensed_items_purchases_api
from ._exceptions_handlers import handle_plugin_requests_exceptions
from ._models import (
    LicensedItemsPurchasesListQueryParams,
    LicensedItemsPurchasesPathParams,
    LicensedItemsRequestContext,
)

_logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


@routes.get(
    f"/{VTAG}/licensed-items-purchases/{{licensed_item_purchase_id}}",
    name="get_licensed_item_purchase",
)
@login_required
@permission_required("catalog/licensed-items.*")
@handle_plugin_requests_exceptions
async def get_licensed_item_purchase(request: web.Request):
    req_ctx = LicensedItemsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        LicensedItemsPurchasesPathParams, request
    )

    licensed_item_purchase_get: LicensedItemPurchaseGet = (
        await _licensed_items_purchases_api.get_licensed_item_purchase(
            app=request.app,
            product_name=req_ctx.product_name,
            user_id=req_ctx.user_id,
            licensed_item_purchase_id=path_params.licensed_item_purchase_id,
        )
    )

    return envelope_json_response(licensed_item_purchase_get)


@routes.get(
    f"/{VTAG}/wallets/{{wallet_id}}/licensed-items-purchases",
    name="list_wallet_licensed_items_purchases",
)
@login_required
@permission_required("catalog/licensed-items.*")
@handle_plugin_requests_exceptions
async def list_wallet_licensed_items_purchases(request: web.Request):
    req_ctx = LicensedItemsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(WalletsPathParams, request)
    query_params: LicensedItemsPurchasesListQueryParams = (
        parse_request_query_parameters_as(
            LicensedItemsPurchasesListQueryParams, request
        )
    )

    licensed_item_purchase_get_page: LicensedItemPurchaseGetPage = (
        await _licensed_items_purchases_api.list_licensed_items_purchases(
            app=request.app,
            product_name=req_ctx.product_name,
            user_id=req_ctx.user_id,
            wallet_id=path_params.wallet_id,
            offset=query_params.offset,
            limit=query_params.limit,
            order_by=OrderBy.model_construct(**query_params.order_by.model_dump()),
        )
    )

    page = Page[LicensedItemPurchaseGet].model_validate(
        paginate_data(
            chunk=licensed_item_purchase_get_page.items,
            request_url=request.url,
            total=licensed_item_purchase_get_page.total,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )
