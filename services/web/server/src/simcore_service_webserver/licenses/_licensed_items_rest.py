import logging

from aiohttp import web
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemGet,
    LicensedItemGetPage,
)
from models_library.rest_ordering import OrderBy
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
from servicelib.aiohttp import status
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

    licensed_item_get_page: LicensedItemGetPage = (
        await _licensed_items_service.list_licensed_items(
            app=request.app,
            product_name=req_ctx.product_name,
            offset=query_params.offset,
            limit=query_params.limit,
            order_by=OrderBy.model_construct(**query_params.order_by.model_dump()),
        )
    )

    page = Page[LicensedItemGet].model_validate(
        paginate_data(
            chunk=licensed_item_get_page.items,
            request_url=request.url,
            total=licensed_item_get_page.total,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


@routes.get(
    f"/{VTAG}/catalog/licensed-items/{{licensed_item_id}}", name="get_licensed_item"
)
@login_required
@permission_required("catalog/licensed-items.*")
@handle_plugin_requests_exceptions
async def get_licensed_item(request: web.Request):
    req_ctx = LicensedItemsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(LicensedItemsPathParams, request)

    licensed_item_get: LicensedItemGet = (
        await _licensed_items_service.get_licensed_item(
            app=request.app,
            licensed_item_id=path_params.licensed_item_id,
            product_name=req_ctx.product_name,
        )
    )

    return envelope_json_response(licensed_item_get)


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

    await _licensed_items_service.purchase_licensed_item(
        app=request.app,
        user_id=req_ctx.user_id,
        licensed_item_id=path_params.licensed_item_id,
        product_name=req_ctx.product_name,
        body_params=body_params,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
