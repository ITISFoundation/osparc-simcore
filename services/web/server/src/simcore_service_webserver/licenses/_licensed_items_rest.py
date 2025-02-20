import logging

from aiohttp import web
from models_library.api_schemas_webserver.licensed_items import LicensedItemRestGet
from models_library.api_schemas_webserver.licensed_items_purchases import (
    LicensedItemPurchaseGet,
)
from models_library.licenses import LicensedItemPage
from models_library.rest_ordering import OrderBy
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _licensed_items_service
from ._common.exceptions_handlers import handle_plugin_requests_exceptions
from ._common.models import (
    LicensedItemsBodyParams,
    LicensedItemsListQueryParams,
    LicensedItemsPathParams,
    LicensedItemsRequestContext,
)

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.get(f"/{VTAG}/catalog/licensed-items", name="list_licensed_items")
@login_required
@permission_required("catalog/licensed-items.*")
@handle_plugin_requests_exceptions
async def list_licensed_items(request: web.Request):
    req_ctx = LicensedItemsRequestContext.model_validate(request)
    query_params: LicensedItemsListQueryParams = parse_request_query_parameters_as(
        LicensedItemsListQueryParams, request
    )

    licensed_item_page: LicensedItemPage = (
        await _licensed_items_service.list_licensed_items(
            app=request.app,
            product_name=req_ctx.product_name,
            include_hidden_items_on_market=False,
            offset=query_params.offset,
            limit=query_params.limit,
            order_by=OrderBy.model_construct(**query_params.order_by.model_dump()),
        )
    )

    page = Page[LicensedItemRestGet].model_validate(
        paginate_data(
            chunk=[
                LicensedItemRestGet.from_domain_model(licensed_item)
                for licensed_item in licensed_item_page.items
            ],
            total=licensed_item_page.total,
            limit=query_params.limit,
            offset=query_params.offset,
            request_url=request.url,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


@routes.post(
    f"/{VTAG}/catalog/licensed-items/{{licensed_item_id}}:purchase",
    name="purchase_licensed_item",
)
@login_required
@permission_required("catalog/licensed-items.*")
@handle_plugin_requests_exceptions
async def purchase_licensed_item(request: web.Request):
    req_ctx = LicensedItemsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(LicensedItemsPathParams, request)
    body_params = await parse_request_body_as(LicensedItemsBodyParams, request)

    purchased_item = await _licensed_items_service.purchase_licensed_item(
        app=request.app,
        user_id=req_ctx.user_id,
        licensed_item_id=path_params.licensed_item_id,
        product_name=req_ctx.product_name,
        body_params=body_params,
    )

    output = LicensedItemPurchaseGet(
        licensed_item_purchase_id=purchased_item.licensed_item_purchase_id,
        product_name=purchased_item.product_name,
        licensed_item_id=purchased_item.licensed_item_id,
        key=purchased_item.key,
        version=purchased_item.version,
        wallet_id=purchased_item.wallet_id,
        pricing_unit_cost_id=purchased_item.pricing_unit_cost_id,
        pricing_unit_cost=purchased_item.pricing_unit_cost,
        start_at=purchased_item.start_at,
        expire_at=purchased_item.expire_at,
        num_of_seats=purchased_item.num_of_seats,
        purchased_by_user=purchased_item.purchased_by_user,
        user_email=purchased_item.user_email,
        purchased_at=purchased_item.purchased_at,
        modified_at=purchased_item.modified,
    )

    return envelope_json_response(output)
