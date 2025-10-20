from typing import Annotated, Generic

from common_library.basic_types import DEFAULT_FACTORY
from common_library.json_serialization import json_dumps
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
)
from pydantic.generics import GenericModel

from .basic_types import IDStr
from .list_operations import OrderClause, OrderDirection, TField, check_ordering_list
from .rest_base import RequestParameters
from .utils.common_validators import (
    parse_json_pre_validator,
)

__all__: tuple[str, ...] = ("OrderDirection",)


class OrderBy(BaseModel):
    # NOTE: use instead OrderClause[TField] where TField is Literal of valid fields
    field: Annotated[IDStr, Field(description="field name identifier")]
    direction: Annotated[
        OrderDirection,
        Field(
            description=(
                f"As [A,B,C,...] if `{OrderDirection.ASC.value}`"
                f" or [Z,Y,X, ...] if `{OrderDirection.DESC.value}`"
            )
        ),
    ] = OrderDirection.ASC


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

    order_by_example = _OrderBy.model_json_schema()["examples"][0]
    order_by_example_json = json_dumps(order_by_example)

    assert _OrderBy.model_validate(order_by_example), "Example is invalid"  # nosec

    converted_default = _OrderBy.model_validate(
        # NOTE: enforces ordering_fields_api_to_column_map
        default.model_dump()
    )

    class _OrderJsonQueryParams(_BaseOrderQueryParams):
        order_by: Annotated[
            _OrderBy,
            BeforeValidator(parse_json_pre_validator),
            Field(
                description=(
                    f"Order by field (`{msg_field_options}`) and direction (`{msg_direction_options}`). "
                    f"The default sorting order is `{json_dumps(default)}`."
                ),
                examples=[order_by_example],
                json_schema_extra={"example_json": order_by_example_json},
            ),
        ] = converted_default

    return _OrderJsonQueryParams


class OrderingQueryParams(GenericModel, Generic[TField]):
    # NOTE: OrderingQueryParams is a more flexible variant for generic usage and that
    #      does include multiple ordering clauses
    #
    order_by: Annotated[
        list[OrderClause[TField]],
        Field(
            default_factory=list,
            description="Order by clauses e.g. ?order_by=-created_at,name",
        ),
    ] = DEFAULT_FACTORY

    @field_validator("order_by", mode="before")
    @classmethod
    def _parse_order_by_string(cls, v):
        """Parses a comma-separated string into a list of OrderClause

        Example, given the query parameter `order_by` in a request like `GET /items?order_by=-created_at,name`
        It parses to:
            [
                OrderClause(field="created_at", direction=OrderDirection.DESC),
                OrderClause(field="name", direction=OrderDirection.ASC),
            ]
        """
        if not v:
            return []

        if isinstance(v, str):
            # 1. from comma-separated string to list of OrderClause
            v = v.split(",")
            clauses: list[tuple[str, OrderDirection]] = []
            for t in v:
                token = t.strip()
                if not token:
                    continue
                if token.startswith("-"):
                    clauses.append((token[1:].strip(), OrderDirection.DESC))
                elif token.startswith("+"):
                    clauses.append((token[1:].strip(), OrderDirection.ASC))
                else:
                    clauses.append((token, OrderDirection.ASC))
            # 2. check for duplicates and conflicting directions
            return [
                {"field": field, "direction": direction}
                for field, direction in check_ordering_list(clauses)
            ]

        # NOTE: Parses ONLY strings into list[OrderClause], otherwise raises TypeError
        msg = f"Invalid type for order_by: expected str, got {type(v)}"
        raise TypeError(msg)
