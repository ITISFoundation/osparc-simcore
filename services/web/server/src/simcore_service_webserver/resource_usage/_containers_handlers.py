from typing import Any

from aiohttp import web
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    Page,
)
from models_library.rest_pagination_utils import paginate_data
from models_library.users import UserID
from pydantic import BaseModel, Extra, Field, NonNegativeInt
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from . import _containers_api as api

#
# API components/schemas
#


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[pydantic-alias]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[pydantic-alias]


class _ListContainersPathParams(BaseModel):
    limit: int = Field(
        default=DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        description="maximum number of items to return (pagination)",
        ge=1,
        lt=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    )
    offset: NonNegativeInt = Field(
        default=0, description="index to the first item to return (pagination)"
    )

    class Config:
        extra = Extra.forbid


#
# API handlers
#

routes = web.RouteTableDef()


@routes.get(f"/{VTAG}/resource-usage/containers", name="list_resource_usage_containers")
@login_required
@permission_required("resource-usage.read")
async def list_resource_usage_containers(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_ListContainersPathParams, request)

    containers: dict = await api.list_containers_usage_by_user_name_and_product(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        offset=query_params.offset,
        limit=query_params.limit,
    )

    page = Page[dict[str, Any]].parse_obj(
        paginate_data(
            chunk=containers["items"],
            request_url=request.url,
            total=containers["total"],
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )
