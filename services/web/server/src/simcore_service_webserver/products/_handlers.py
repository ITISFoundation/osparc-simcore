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
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


@routes.get(f"/{VTAG}/credits-price", name="get_current_product_price")
@login_required
@permission_required("product.price.read")
async def _get_current_product_price(request: web.Request):
    req_ctx = _ProductsRequestContext.parse_obj(request)
    price_info = await _api.get_current_product_credit_price_info(request)

    credit_price = GetCreditPrice(
        product_name=req_ctx.product_name,
        usd_per_credit=price_info.usd_per_credit if price_info else None,  # type: ignore[arg-type]
        min_payment_amount_usd=price_info.min_payment_amount_usd  # type: ignore[arg-type]
        if price_info
        else None,
    )
    return envelope_json_response(credit_price)


class _ProductsRequestParams(StrictRequestParams):
    product_name: IDStr | Literal["current"]


@routes.get(f"/{VTAG}/products/{{product_name}}", name="get_product")
@login_required
@permission_required("product.details.*")
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
    data = GetProduct(**product.dict(), templates=[])
    return envelope_json_response(data)


class _ProductTemplateParams(_ProductsRequestParams):
    template_id: IDStr


@routes.put(
    f"/{VTAG}/products/{{product_name}}/templates/{{template_id}}",
    name="update_product_template",
)
@login_required
@permission_required("product.details.*")
async def update_product_template(request: web.Request):
    req_ctx = _ProductsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_ProductTemplateParams, request)

    assert req_ctx  # nosec
    assert path_params  # nosec

    raise NotImplementedError
