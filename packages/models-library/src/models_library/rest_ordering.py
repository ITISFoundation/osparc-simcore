from enum import Enum
from typing import Any, ClassVar

from models_library.utils.json_serialization import json_dumps, json_loads
from pydantic import BaseModel, Field, Json, validator

from .basic_types import IDStr
from .rest_base import RequestParameters


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


def create_order_by_query_model_classes(
    *,
    sortable_fields: set[str],
    default_order_by: OrderBy,
    override_direction_default: bool = False,
) -> tuple[type[_BaseOrderByQueryParams], type[BaseModel]]:
    """
    Factory to create an uniform model used as ordering parameters in a query

    Returns the validation
    """

    assert default_order_by.field in sortable_fields  # nosec

    msg_field_options = "|".join(sorted(sortable_fields))
    msg_direction_options = "|".join(sorted(OrderDirection))
    order_by_example: dict[str, Any] = OrderBy.Config.schema_extra["example"]

    class _OrderByJsonable(OrderBy):
        direction: OrderDirection = Field(
            default=default_order_by.direction
            if override_direction_default
            else OrderBy.__fields__["direction"].default,
            description=OrderBy.__fields__["direction"].field_info.description,
        )

        @classmethod
        def __modify_schema__(cls, field_schema: dict[str, Any]) -> None:
            # openapi.json schema is corrected here
            field_schema.update(
                type="string",
                format="json-string",
                default=json_dumps(default_order_by),
                example=json_dumps(order_by_example),
                title="Order By",
            )

        @validator("field", allow_reuse=True)
        @classmethod
        def _check_if_sortable_field(cls, v):
            if v not in sortable_fields:
                msg = (
                    f"We do not support ordering by provided field '{v}'. "
                    f"Fields supported are {msg_field_options}."
                )
                raise ValueError(msg)
            return v

    description = (
        f"Order by field ({msg_field_options}) and direction ({msg_direction_options}). "
        f"The default sorting order is '{default_order_by.direction.value}' on '{default_order_by.field}'."
    )

    class _RequestValidatorModel(_BaseOrderByQueryParams):
        # Used in rest handler for verification
        order_by: _OrderByJsonable = Field(
            default=default_order_by,
            description=description,
        )

        @validator("order_by", allow_reuse=True, pre=True)
        @classmethod
        def _pre_parse_if_json(cls, v):
            if isinstance(v, str):
                # can raise a JsonEncoderError(TypeError)
                return json_loads(v)
            return v

    class _OpenapiModel(BaseModel):
        # Used to produce nice openapi.json specs
        order_by: Json = Field(
            default=json_dumps(default_order_by),
            description=description,
        )

        class Config:
            schema_extra: ClassVar[dict[str, Any]] = {
                "title": "Order By Parameters",
            }

    return _RequestValidatorModel, _OpenapiModel
