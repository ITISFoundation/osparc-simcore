from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, BeforeValidator, Field

from .utils.common_validators import parse_json_pre_validator


class Filters(BaseModel):
    """
    Encoded as JSON. Each available filter can have its own logic (should be well documented)
    Inspired by Docker API https://docs.docker.com/engine/api/v1.43/#tag/Container/operation/ContainerList.
    """


# Custom filter
FilterT = TypeVar("FilterT", bound=Filters)


class FiltersQueryParameters(BaseModel, Generic[FilterT]):
    filters: Annotated[
        FilterT | None, BeforeValidator(parse_json_pre_validator)
    ] = Field(  # pylint: disable=unsubscriptable-object
        default=None,
        description="Custom filter query parameter encoded as JSON",
    )
