from typing import Annotated

from models_library.basic_types import IDStr
from models_library.functions import FunctionID
from models_library.groups import GroupID
from models_library.rest_base import RequestParameters
from models_library.rest_filters import Filters, FiltersQueryParameters
from models_library.rest_ordering import (
    OrderBy,
    OrderDirection,
    create_ordering_query_model_class,
)
from models_library.rest_pagination import PageQueryParameters
from pydantic import BaseModel, ConfigDict, Field

from ...models import AuthenticatedRequestContext

assert AuthenticatedRequestContext.__name__  # nosec


class FunctionPathParams(BaseModel):
    function_id: FunctionID
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class FunctionGroupPathParams(FunctionPathParams):
    group_id: GroupID


class FunctionQueryParams(BaseModel):
    include_extras: bool = False


class FunctionGetQueryParams(FunctionQueryParams): ...


class FunctionFilters(Filters):
    search_by_title: Annotated[
        str | None,
        Field(
            description="A search query to filter functions by their title. This field performs a case-insensitive partial match against the function title field.",
        ),
    ] = None


FunctionListOrderQueryParams: type[RequestParameters] = (
    create_ordering_query_model_class(
        ordering_fields={
            "created_at",
            "modified_at",
            "name",
        },
        default=OrderBy(field=IDStr("modified_at"), direction=OrderDirection.DESC),
        ordering_fields_api_to_column_map={
            "created_at": "created",
            "modified_at": "modified",
        },
    )
)


class FunctionsListExtraQueryParams(RequestParameters):
    search: Annotated[
        str | None,
        Field(
            description="Multi column full text search",
            max_length=100,
            examples=["My Function"],
        ),
    ] = None


class FunctionsListQueryParams(
    PageQueryParameters,
    FunctionListOrderQueryParams,  # type: ignore[misc, valid-type]
    FiltersQueryParameters[FunctionFilters],
    FunctionsListExtraQueryParams,
    FunctionQueryParams,
): ...


class FunctionDeleteQueryParams(BaseModel):
    force: Annotated[
        bool,
        Field(
            description="If true, deletes the function even if it has associated jobs; otherwise, returns HTTP_409_CONFLICT if jobs exist.",
        ),
    ] = False


__all__: tuple[str, ...] = ("AuthenticatedRequestContext",)
