import logging

from aiohttp import web
from models_library.api_schemas_webserver.license_goods import (
    LicenseGoodGet,
    LicenseGoodGetPage,
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
from . import _license_goods_api
from ._exceptions_handlers import handle_plugin_requests_exceptions
from ._models import (
    LicenseGoodsBodyParams,
    LicenseGoodsListQueryParams,
    LicenseGoodsPathParams,
    LicenseGoodsRequestContext,
)

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.get(f"/{VTAG}/license-goods", name="list_license_goods")
@login_required
@permission_required("license-goods.*")
@handle_plugin_requests_exceptions
async def list_workspaces(request: web.Request):
    req_ctx = LicenseGoodsRequestContext.model_validate(request)
    query_params: LicenseGoodsListQueryParams = parse_request_query_parameters_as(
        LicenseGoodsListQueryParams, request
    )

    license_good_get_page: LicenseGoodGetPage = (
        await _license_goods_api.list_license_goods(
            app=request.app,
            product_name=req_ctx.product_name,
            offset=query_params.offset,
            limit=query_params.limit,
            order_by=OrderBy.model_construct(**query_params.order_by.model_dump()),
        )
    )

    page = Page[LicenseGoodGet].model_validate(
        paginate_data(
            chunk=license_good_get_page.items,
            request_url=request.url,
            total=license_good_get_page.total,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


@routes.get(f"/{VTAG}/license-goods/{{license_good_id}}", name="get_license_good")
@login_required
@permission_required("license-goods.*")
@handle_plugin_requests_exceptions
async def get_workspace(request: web.Request):
    req_ctx = LicenseGoodsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(LicenseGoodsPathParams, request)

    license_good_get: LicenseGoodGet = await _license_goods_api.get_license_good(
        app=request.app,
        license_good_id=path_params.license_good_id,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(license_good_get)


@routes.post(
    f"/{VTAG}/license-goods/{{license_good_id}}:purchase",
    name="purchase_license_good",
)
@login_required
@permission_required("license-goods.*")
@handle_plugin_requests_exceptions
async def purchase_license_good(request: web.Request):
    req_ctx = LicenseGoodsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(LicenseGoodsPathParams, request)
    body_params = await parse_request_body_as(LicenseGoodsBodyParams, request)

    await _license_goods_api.purchase_license_good(
        app=request.app,
        user_id=req_ctx.user_id,
        license_good_id=path_params.license_good_id,
        product_name=req_ctx.product_name,
        body_params=body_params,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
