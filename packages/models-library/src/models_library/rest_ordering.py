from enum import Enum
from typing import Any, ClassVar

from models_library.utils.json_serialization import json_dumps
from pydantic import BaseModel, Field, validator

from .basic_types import IDStr
from .rest_base import RequestParameters
from .utils.common_validators import load_if_json_encoded_pre_validator


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


class _BaseOrderByQueryParams(RequestParameters):
    order_by: OrderBy | None = None


def create_ordering_query_model_classes(
    *,
    ordering_fields: set[str],
    default: OrderBy,
    override_direction_default: bool = False,
) -> tuple[type[_BaseOrderByQueryParams], type[BaseModel]]:
    """
    Factory to create an uniform model used as ordering parameters in a query

    Returns the validation
    """

    assert default.field in ordering_fields  # nosec

    order_by_example: dict[str, Any] = OrderBy.Config.schema_extra["example"]
    msg_field_options = "|".join(sorted(ordering_fields))
    msg_direction_options = "|".join(sorted(OrderDirection))
    description = (
        f"Order by field ({msg_field_options}) and direction ({msg_direction_options}). "
        f"The default sorting order is '{default.direction.value}' on '{default.field}'."
        f"For instance order_by={json_dumps(order_by_example)}"
    )

    class _OrderBy(OrderBy):
        direction: OrderDirection = Field(
            default=default.direction
            if override_direction_default
            else OrderBy.__fields__["direction"].default,
            description=OrderBy.__fields__["direction"].field_info.description,
        )

        @validator("field", allow_reuse=True)
        @classmethod
        def _check_if_ordering_field(cls, v):
            if v not in ordering_fields:
                msg = (
                    f"We do not support ordering by provided field '{v}'. "
                    f"Fields supported are {msg_field_options}."
                )
                raise ValueError(msg)
            return v

    class _RequestValidatorModel(_BaseOrderByQueryParams):
        # Used in rest handler for verification
        order_by: _OrderBy = Field(default=default)

        _pre_parse_string = validator("order_by", allow_reuse=True, pre=True)(
            load_if_json_encoded_pre_validator
        )

    # -------

    class _OrderByJson(str):
        __slots__ = ()

        @classmethod
        def __modify_schema__(cls, field_schema: dict[str, Any]) -> None:
            # openapi.json schema is corrected here
            field_schema.update(
                type="string",
                format="json-string",
                description=description,
            )

    class _OpenApiModel(BaseModel):
        # Used to produce nice openapi.json specs
        order_by: _OrderByJson = Field(default=json_dumps(default))

    return _RequestValidatorModel, _OpenApiModel
