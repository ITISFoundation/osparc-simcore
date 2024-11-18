from enum import Enum
from typing import Any, ClassVar

from models_library.utils.json_serialization import json_dumps
from pydantic import BaseModel, Extra, Field, validator

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


class _BaseOrderQueryParams(RequestParameters):
    order_by: OrderBy | None = None


def create_ordering_query_model_classes(
    *,
    ordering_fields: set[str],
    default: OrderBy,
    ordering_fields_api_to_column_map: dict[str, str] | None = None,
) -> type[_BaseOrderQueryParams]:
    """Factory to create an uniform model used as ordering parameters in a query

    Arguments:
        ordering_fields -- A set of valid fields that can be used for ordering.
            These should correspond to API field names.
        default -- The default ordering configuration to be applied if no explicit
            ordering is provided

    Keyword Arguments:
        ordering_fields_api_to_column_map -- A mapping of API field names to
            database column names. If provided, fields specified in the API
            will be automatically translated to their corresponding database
            column names for seamless integration with database queries.
    """
    _ordering_fields_api_to_column_map = ordering_fields_api_to_column_map or {}

    assert set(_ordering_fields_api_to_column_map.keys()).issubset(  # nosec
        ordering_fields
    )

    assert default.field in ordering_fields  # nosec

    msg_field_options = "|".join(sorted(ordering_fields))
    msg_direction_options = "|".join(sorted(OrderDirection))

    class _OrderBy(OrderBy):
        class Config:
            schema_extra: ClassVar[dict[str, Any]] = {
                "example": {
                    "field": next(iter(ordering_fields)),
                    "direction": OrderDirection.DESC.value,
                }
            }
            extra = Extra.forbid
            # Necessary to run _check_ordering_field_and_map in defaults and assignments
            validate_all = True
            validate_assignment = True

        @validator("field", allow_reuse=True, always=True)
        @classmethod
        def _check_ordering_field_and_map(cls, v):
            if v not in ordering_fields:
                msg = (
                    f"We do not support ordering by provided field '{v}'. "
                    f"Fields supported are {msg_field_options}."
                )
                raise ValueError(msg)

            # API field name -> DB column_name conversion
            return _ordering_fields_api_to_column_map.get(v) or v

    order_by_example: dict[str, Any] = _OrderBy.Config.schema_extra["example"]
    order_by_example_json = json_dumps(order_by_example)
    assert _OrderBy.parse_obj(order_by_example), "Example is invalid"  # nosec

    converted_default = _OrderBy.parse_obj(
        # NOTE: enforces ordering_fields_api_to_column_map
        default.dict()
    )

    class _OrderQueryParams(_BaseOrderQueryParams):
        order_by: _OrderBy = Field(
            default=converted_default,
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
