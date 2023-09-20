import logging

from aiohttp import web
from models_library.api_schemas_webserver.product import CreditPriceGet
from models_library.users import UserID
from pydantic import Field
from servicelib.aiohttp.requests_validation import RequestParams
from servicelib.request_keys import RQT_USERID_KEY
from simcore_service_webserver.utils_aiohttp import envelope_json_response

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from . import _api

routes = web.RouteTableDef()


_logger = logging.getLogger(__name__)


class _ProductsRequestContext(RequestParams):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)


@routes.get(f"/{VTAG}/credits-price", name="get_current_product_price")
@login_required
@permission_required("product.price.read")
async def get_current_product_price(request: web.Request):
    req_ctx = _ProductsRequestContext.parse_obj(request)

    credit_price = CreditPriceGet(
        product_name=req_ctx.product_name,
        usd_per_credit=await _api.get_current_product_credit_price(request),
    )
    return envelope_json_response(credit_price)
