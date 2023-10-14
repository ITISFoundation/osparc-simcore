import logging
from typing import Literal

from aiohttp import web
from models_library.api_schemas_webserver.product import GetCreditPrice, GetProduct
from models_library.basic_types import IDStr
from models_library.users import UserID
from pydantic import Extra, Field
from servicelib.aiohttp.requests_validation import (
    RequestParams,
    StrictRequestParams,
    parse_request_path_parameters_as,
)
from servicelib.request_keys import RQT_USERID_KEY
from simcore_service_webserver.utils_aiohttp import envelope_json_response

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from . import _api, api
from ._model import Product

routes = web.RouteTableDef()


_logger = logging.getLogger(__name__)


class _ProductsRequestContext(RequestParams):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)


@routes.get(f"/{VTAG}/credits-price", name="get_current_product_price")
@login_required
@permission_required("product.price.read")
async def _get_current_product_price(request: web.Request):
    req_ctx = _ProductsRequestContext.parse_obj(request)

    credit_price = GetCreditPrice(
        product_name=req_ctx.product_name,
        usd_per_credit=await _api.get_current_product_credit_price(request),
    )
    return envelope_json_response(credit_price)


class _ProductsRequestParams(StrictRequestParams):
    product_name: IDStr | Literal["current"]


@routes.get(f"/{VTAG}/products/{{product_name}}", name="get_product")
@login_required
@permission_required("product.details.read")
async def _get_product(request: web.Request):
    req_ctx = _ProductsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_ProductsRequestParams, request)

    if path_params.product_name == "current":
        product_name = req_ctx.product_name
    else:
        product_name = path_params.product_name

    try:
        product: Product = api.get_product(request.app, product_name=product_name)
    except KeyError as err:
        raise web.HTTPNotFound(reason=f"{product_name=} not found") from err

    assert GetProduct.Config.extra == Extra.ignore  # nosec
    data = GetProduct(**product.dict())
    return envelope_json_response(data)
