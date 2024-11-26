from enum import Enum
from typing import Annotated

from common_library.json_serialization import json_dumps
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

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
    order_by: OrderBy


def create_ordering_query_model_class(
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
        model_config = ConfigDict(
            extra="forbid",
            json_schema_extra={
                "examples": [
                    {
                        "field": next(iter(ordering_fields)),
                        "direction": OrderDirection.DESC.value,
                    }
                ]
            },
            # Necessary to run _check_ordering_field_and_map in defaults and assignments
            validate_assignment=True,
            validate_default=True,
        )

        @field_validator("field", mode="before")
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

    assert "json_schema_extra" in _OrderBy.model_config  # nosec
    assert isinstance(_OrderBy.model_config["json_schema_extra"], dict)  # nosec
    assert isinstance(  # nosec
        _OrderBy.model_config["json_schema_extra"]["examples"], list
    )
    order_by_example = _OrderBy.model_config["json_schema_extra"]["examples"][0]
    order_by_example_json = json_dumps(order_by_example)
    assert _OrderBy.model_validate(order_by_example), "Example is invalid"  # nosec

    converted_default = _OrderBy.model_validate(
        # NOTE: enforces ordering_fields_api_to_column_map
        default.model_dump()
    )

    class _OrderQueryParams(_BaseOrderQueryParams):
        order_by: Annotated[
            _OrderBy, BeforeValidator(parse_json_pre_validator)
        ] = Field(
            default=converted_default,
            description=(
                f"Order by field (`{msg_field_options}`) and direction (`{msg_direction_options}`). "
                f"The default sorting order is `{json_dumps(default)}`."
            ),
            examples=[order_by_example],
            json_schema_extra={"example_json": order_by_example_json},
        )

    return _OrderQueryParams
