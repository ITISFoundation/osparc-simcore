from typing import Annotated, Final, Generic, TypeAlias, TypeVar

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    TypeAdapter,
    ValidationInfo,
    field_validator,
)

from .rest_base import RequestParameters
from .utils.common_validators import none_to_empty_list_pre_validator

# Default limit values
#  - Using same values across all pagination entrypoints simplifies
#    interconnecting paginated calls
MINIMUM_NUMBER_OF_ITEMS_PER_PAGE: Final[int] = 1
MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE: Final[int] = 50

PageLimitInt: TypeAlias = Annotated[
    int,
    Field(
        ge=MINIMUM_NUMBER_OF_ITEMS_PER_PAGE,
        le=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
        description="The maximum number of items to return in a single page.",
    ),
]
PageOffsetInt: TypeAlias = Annotated[
    int,
    Field(
        ge=0,
        description="The number of items to skip before starting to collect the items for the current pag",
    ),
]
PageTotalCount: TypeAlias = NonNegativeInt


DEFAULT_NUMBER_OF_ITEMS_PER_PAGE: Final[PageLimitInt] = TypeAdapter(
    PageLimitInt
).validate_python(20)


class CursorQueryParameters(RequestParameters):
    """Query parameters for Cursor-Based Pagination

    SEE https://uriyyo-fastapi-pagination.netlify.app/learn/pagination/techniques/#cursor-based-pagination
    """

    size: PageLimitInt = Field(
        default=DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        description="maximum number of items to return (pagination)",
    )
    cursor: Annotated[
        str | None,
        Field(
            description="unique identifier that represent the position in the dataset"
        ),
    ] = None


class PageQueryParameters(RequestParameters):
    """Query parameters for Limit-Offset Pagination

    SEE https://uriyyo-fastapi-pagination.netlify.app/learn/pagination/techniques/#limit-offset-pagination
    """

    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE
    offset: PageOffsetInt = 0


class PageMetaInfoLimitOffset(BaseModel):
    limit: PositiveInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE
    total: PageTotalCount
    offset: NonNegativeInt = 0
    count: NonNegativeInt

    @field_validator("offset")
    @classmethod
    def _check_offset(cls, v, info: ValidationInfo):
        if v > 0 and v >= info.data["total"]:
            msg = f"offset {v} cannot be equal or bigger than total {info.data['total']}, please check"
            raise ValueError(msg)
        return v

    @field_validator("count")
    @classmethod
    def _check_count(cls, v, info: ValidationInfo):
        if v > info.data["limit"]:
            msg = f"count {v} bigger than limit {info.data['limit']}, please check"
            raise ValueError(msg)
        if v > info.data["total"]:
            msg = f"count {v} bigger than expected total {info.data['total']}, please check"
            raise ValueError(msg)
        if "offset" in info.data and (info.data["offset"] + v) > info.data["total"]:
            msg = f"offset {info.data['offset']} + count {v} is bigger than allowed total {info.data['total']}, please check"
            raise ValueError(msg)
        return v

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"total": 7, "count": 4, "limit": 4, "offset": 0},
            ]
        },
    )


RefT = TypeVar("RefT")


class PageRefs(BaseModel, Generic[RefT]):
    self: RefT
    first: RefT
    prev: RefT | None
    next: RefT | None
    last: RefT

    model_config = ConfigDict(extra="forbid")


class PageLinks(
    PageRefs[
        Annotated[
            str,
            BeforeValidator(lambda x: str(TypeAdapter(AnyHttpUrl).validate_python(x))),
        ]
    ]
): ...


ItemT = TypeVar("ItemT")


class Page(BaseModel, Generic[ItemT]):
    """
    Paginated response model of ItemTs
    """

    meta: PageMetaInfoLimitOffset = Field(alias="_meta")
    links: PageLinks = Field(alias="_links")
    data: list[ItemT]

    _none_is_empty = field_validator("data", mode="before")(
        none_to_empty_list_pre_validator
    )

    @field_validator("data")
    @classmethod
    def _check_data_compatible_with_meta(cls, v, info: ValidationInfo):
        if "meta" not in info.data:
            # if the validation failed in meta this happens
            msg = "meta not in values"
            raise ValueError(msg)
        if len(v) != info.data["meta"].count:
            msg = f"container size [{len(v)}] must be equal to count [{info.data['meta'].count}]"
            raise ValueError(msg)
        return v

    model_config = ConfigDict(extra="forbid")
