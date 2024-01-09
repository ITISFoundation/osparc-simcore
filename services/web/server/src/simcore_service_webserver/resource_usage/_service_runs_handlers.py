import datetime
import functools
import json
import re
from datetime import datetime, timezone
from typing import Any

from aiohttp import web
from models_library.resource_tracker import ServiceResourceUsagesFilters, StartedAt
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    Page,
)
from models_library.rest_pagination_utils import paginate_data
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, Extra, Field, NonNegativeInt, validator
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..wallets.errors import WalletAccessForbiddenError
from . import _service_runs_api as api

#
# API components/schemas
#


def _handle_resource_usage_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except WalletAccessForbiddenError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[pydantic-alias]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[pydantic-alias]


def _replace_multiple_spaces(text: str) -> str:
    # Use regular expression to replace multiple spaces with a single space
    cleaned_text = re.sub(r"\s+", " ", text)
    return cleaned_text


class _ListServicesResourceUsagesPathParams(BaseModel):
    limit: int = Field(
        default=DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        description="maximum number of items to return (pagination)",
        ge=1,
        lt=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    )
    offset: NonNegativeInt = Field(
        default=0, description="index to the first item to return (pagination)"
    )
    wallet_id: WalletID = Field(default=None)
    order_by: list[OrderBy] = Field(
        default=None,
        description="Sorting field. The default sorting order is ascending. To specify descending order for a field, users append a 'desc' suffix",
        example="foo desc, bar",
    )
    filters: ServiceResourceUsagesFilters = Field(
        default=None,
        description="Filters to process on the resource usages list, encoded as JSON. Currently supports the filtering of 'started_at' field with 'from' and 'until' parameters in <yyyy-mm-dd> format. The date range specidied is inclusive.",
        example='{"started_at": {"from": "yyyy-mm-dd", "until": "yyyy-mm-dd"}}',
    )

    @validator("order_by", pre=True)
    @classmethod
    def order_by_should_have_special_format(cls, v):
        if v:
            parse_fields_with_direction = []
            fields = v.split(",")
            for field in fields:
                field_info = _replace_multiple_spaces(field.strip()).split(" ")
                field_name = field_info[0]
                if not field_name:
                    msg = "order_by parameter is not parsable"
                    raise ValueError(msg)
                direction = OrderDirection.ASC

                if len(field_info) == 2:  # noqa: PLR2004
                    if field_info[1] == OrderDirection.DESC.value:
                        direction = OrderDirection.DESC
                    else:
                        msg = "Field direction in the order_by parameter must contain either 'desc' direction or empty value for 'asc' direction."
                        raise ValueError(msg)

                parse_fields_with_direction.append(
                    OrderBy(field=field_name, direction=direction)
                )

            # check valid field values
            for item in parse_fields_with_direction:
                if item.field not in {"started_at", "stopped_at", "credit_cost"}:
                    msg = f"We do not support ordering by provided field {item.field}"
                    raise ValueError(msg)

            return parse_fields_with_direction

        msg = "Unexpected error occured."
        raise RuntimeError(msg)

    @validator("filters", pre=True)
    @classmethod
    def filters_parse_to_object(cls, v):
        if v:
            try:
                v = json.loads(v)
            except Exception as exc:
                msg = "Unable to decode filters parameter. Please double check whether it is proper JSON format."
                raise ValueError(msg) from exc

            for key, value in v.items():
                if key not in {"started_at"}:
                    msg = f"We do not support filtering by provided field {key}"
                    raise ValueError(msg)

                if key == "started_at":
                    try:
                        from_ = datetime.strptime(value["from"], "%Y-%m-%d").replace(
                            tzinfo=timezone.utc
                        )
                        until = datetime.strptime(value["until"], "%Y-%m-%d").replace(
                            tzinfo=timezone.utc
                        )
                    except Exception as exc:
                        msg = "Both 'from' and 'until' keys must be provided in proper format <yyyy-mm-dd>."
                        raise ValueError(msg) from exc
                    return ServiceResourceUsagesFilters(
                        started_at=StartedAt(from_=from_, until=until)
                    )
        msg = "Unexpected error occured."
        raise RuntimeError(msg)

    class Config:
        extra = Extra.forbid


#
# API handlers
#

routes = web.RouteTableDef()


@routes.get(f"/{VTAG}/services/-/resource-usages", name="list_resource_usage_services")
@login_required
@permission_required("resource-usage.read")
@_handle_resource_usage_exceptions
async def list_resource_usage_services(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(
        _ListServicesResourceUsagesPathParams, request
    )

    services: dict = await api.list_usage_services(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        wallet_id=query_params.wallet_id,
        offset=query_params.offset,
        limit=query_params.limit,
        order_by=query_params.order_by,
        filters=query_params.filters,
    )

    page = Page[dict[str, Any]].parse_obj(
        paginate_data(
            chunk=services["items"],
            request_url=request.url,
            total=services["total"],
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )
