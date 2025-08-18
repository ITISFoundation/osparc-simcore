from models_library.basic_types import IDStr
from models_library.functions import FunctionID
from models_library.rest_base import RequestParameters
from models_library.rest_ordering import (
    OrderBy,
    OrderDirection,
    create_ordering_query_model_class,
)
from models_library.rest_pagination import PageQueryParameters
from pydantic import BaseModel, ConfigDict

from ...models import AuthenticatedRequestContext

assert AuthenticatedRequestContext.__name__  # nosec


class FunctionPathParams(BaseModel):
    function_id: FunctionID
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class _FunctionQueryParams(BaseModel):
    include_extras: bool = False


class FunctionGetQueryParams(_FunctionQueryParams): ...


_FunctionOrderQueryParams: type[RequestParameters] = create_ordering_query_model_class(
    ordering_fields={
        "name",
        "created_at",
        "modified_at",
    },
    default=OrderBy(field=IDStr("modified_at"), direction=OrderDirection.DESC),
)


class FunctionsListQueryParams(
    PageQueryParameters, _FunctionOrderQueryParams, _FunctionQueryParams
): ...


__all__: tuple[str, ...] = ("AuthenticatedRequestContext",)
