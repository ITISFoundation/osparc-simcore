import logging

from aiohttp import web
from models_library.api_schemas_webserver.product import (
    CreditPriceGet,
    ProductGet,
    ProductUIGet,
)
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _service, products_web
from ._repository import ProductRepository
from ._rest_schemas import ProductsRequestContext, ProductsRequestParams
from .models import Product

routes = web.RouteTableDef()


_logger = logging.getLogger(__name__)


@routes.get(f"/{VTAG}/credits-price", name="get_current_product_price")
@login_required
@permission_required("product.price.read")
async def _get_current_product_price(request: web.Request):
    req_ctx = ProductsRequestContext.model_validate(request)
    price_info = await products_web.get_current_product_credit_price_info(request)

    credit_price = CreditPriceGet(
        product_name=req_ctx.product_name,
        usd_per_credit=price_info.usd_per_credit if price_info else None,
        min_payment_amount_usd=(
            price_info.min_payment_amount_usd  # type: ignore[arg-type]
            if price_info
            else None
        ),
    )
    return envelope_json_response(credit_price)


@routes.get(f"/{VTAG}/products/{{product_name}}", name="get_product")
@login_required
@permission_required("product.details.*")
async def _get_product(request: web.Request):
    req_ctx = ProductsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProductsRequestParams, request)

    if path_params.product_name == "current":
        product_name = req_ctx.product_name
    else:
        product_name = path_params.product_name

    try:
        product: Product = _service.get_product(request.app, product_name=product_name)
    except KeyError as err:
        raise web.HTTPNotFound(reason=f"{product_name=} not found") from err

    assert "extra" in ProductGet.model_config  # nosec
    assert ProductGet.model_config["extra"] == "ignore"  # nosec
    data = ProductGet(**product.model_dump(), templates=[])
    return envelope_json_response(data)


@routes.get(f"/{VTAG}/products/current/ui", name="get_current_product_ui")
@login_required
@permission_required("product.ui.read")
async def _get_current_product_ui(request: web.Request):
    req_ctx = ProductsRequestContext.model_validate(request)
    product_name = req_ctx.product_name

    ui = await _service.get_product_ui(
        ProductRepository.create_from_request(request), product_name=product_name
    )

    data = ProductUIGet(product_name=product_name, ui=ui)
    return envelope_json_response(data)
