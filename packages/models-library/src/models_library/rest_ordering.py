from enum import Enum
from typing import Any, ClassVar

from models_library.utils.json_serialization import json_dumps
from pydantic import BaseModel, Field, validator

from .basic_types import IDStr
from .rest_base import RequestParameters
from .utils.common_validators import parse_json_pre_validator


class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class OrderBy(BaseModel):
    # Based on https://google.aip.dev/132#ordering
    field: IDStr = Field(..., description="field name identifier")
    direction: OrderDirection = Field(
        default=OrderDirection.ASC,
        description=(
            f"As [A,B,C,...] if `{OrderDirection.ASC.value}`"
            f" or [Z,Y,X, ...] if `{OrderDirection.DESC.value}`"
        ),
    )

    class Config:
        extra = "forbid"
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {"field": "some_field_name", "direction": "desc"}
        }


class _BaseOrderQueryParams(RequestParameters):
    order_by: OrderBy | None = None


def create_ordering_query_model_classes(
    *,
    ordering_fields: set[str],
    default: OrderBy,
) -> type[_BaseOrderQueryParams]:
    """
    Factory to create an uniform model used as ordering parameters in a query

    """
    assert default.field in ordering_fields  # nosec

    msg_field_options = "|".join(sorted(ordering_fields))
    msg_direction_options = "|".join(sorted(OrderDirection))

    class _OrderBy(OrderBy):
        @validator("field", allow_reuse=True, always=True)
        @classmethod
        def _check_if_ordering_field(cls, v):
            if v not in ordering_fields:
                msg = (
                    f"We do not support ordering by provided field '{v}'. "
                    f"Fields supported are {msg_field_options}."
                )
                raise ValueError(msg)
            return v

    order_by_example: dict[str, Any] = OrderBy.Config.schema_extra["example"]
    order_by_example_json = json_dumps(order_by_example)

    class _OrderQueryParams(_BaseOrderQueryParams):
        order_by: _OrderBy = Field(
            default=default,
            description=(
                f"Order by field (`{msg_field_options}`) and direction (`{msg_direction_options}`). "
                f"The default sorting order is `{json_dumps(default)}`."
            ),
            example=order_by_example,
            example_json=order_by_example_json,
        )

        _pre_parse_string = validator("order_by", allow_reuse=True, pre=True)(
            parse_json_pre_validator
        )

    return _OrderQueryParams
