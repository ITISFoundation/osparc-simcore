import logging
from typing import Literal

from aiohttp import web
from models_library.api_schemas_webserver.product import (
    GetCreditPrice,
    ProductGet,
    ProductUIGet,
)
from models_library.basic_types import IDStr
from models_library.rest_base import RequestParameters, StrictRequestParameters
from models_library.users import UserID
from pydantic import Field
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as
from servicelib.request_keys import RQT_USERID_KEY
from simcore_service_webserver.products._repository import ProductRepository

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _service, service
from ._models import Product

routes = web.RouteTableDef()


_logger = logging.getLogger(__name__)


class _ProductsRequestContext(RequestParameters):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


@routes.get(f"/{VTAG}/credits-price", name="get_current_product_price")
@login_required
@permission_required("product.price.read")
async def _get_current_product_price(request: web.Request):
    req_ctx = _ProductsRequestContext.model_validate(request)
    price_info = await _service.get_current_product_credit_price_info(request)

    credit_price = GetCreditPrice(
        product_name=req_ctx.product_name,
        usd_per_credit=price_info.usd_per_credit if price_info else None,
        min_payment_amount_usd=(
            price_info.min_payment_amount_usd  # type: ignore[arg-type]
            if price_info
            else None
        ),
    )
    return envelope_json_response(credit_price)


class _ProductsRequestParams(StrictRequestParameters):
    product_name: IDStr | Literal["current"]


@routes.get(f"/{VTAG}/products/{{product_name}}", name="get_product")
@login_required
@permission_required("product.details.*")
async def _get_product(request: web.Request):
    req_ctx = _ProductsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_ProductsRequestParams, request)

    if path_params.product_name == "current":
        product_name = req_ctx.product_name
    else:
        product_name = path_params.product_name

    try:
        product: Product = service.get_product(request.app, product_name=product_name)
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
    req_ctx = _ProductsRequestContext.model_validate(request)
    product_name = req_ctx.product_name

    ui = await service.get_product_ui(
        ProductRepository.create_from_request(request), product_name=product_name
    )

    data = ProductUIGet(product_name=product_name, ui=ui)
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
    req_ctx = _ProductsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_ProductTemplateParams, request)

    assert req_ctx  # nosec
    assert path_params  # nosec

    raise NotImplementedError
