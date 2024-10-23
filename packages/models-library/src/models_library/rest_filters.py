from typing import Generic, TypeVar

from pydantic import BaseModel, Field, Json
from pydantic.generics import GenericModel


class Filters(BaseModel):
    """inspired by Docker API https://docs.docker.com/engine/api/v1.43/#tag/Container/operation/ContainerList.
    Encoded as JSON. Each available filter can have its own logic (should be well documented)
    """


# Custom filter
FilterT = TypeVar("FilterT", bound=Filters)


class FiltersQueryParam(GenericModel, Generic[FilterT]):
    filters: Json[FilterT] | None = Field(
        default=None,
        description="Custom filter query parameter encoded JSON",
    )
