from typing import Generic, TypeVar

from pydantic import BaseModel, Field, Json


class Filters(BaseModel):
    """
    Encoded as JSON. Each available filter can have its own logic (should be well documented)
    Inspired by Docker API https://docs.docker.com/engine/api/v1.43/#tag/Container/operation/ContainerList.
    """


# Custom filter
FilterT = TypeVar("FilterT", bound=Filters)


class FiltersQueryParameters(BaseModel, Generic[FilterT]):
    filters: Json[FilterT] | None = Field(  # pylint: disable=unsubscriptable-object
        default=None,
        description="Custom filter query parameter encoded as JSON",
    )
