from typing import Annotated, Any, ClassVar, Generic, cast

from common_library.json_serialization import json_dumps
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

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
                f"As [A,B,C,...] if `{OrderDirection.ASC.value}` or [Z,Y,X, ...] if `{OrderDirection.DESC.value}`"
            )
        ),
    ] = OrderDirection.ASC


class _BaseOrderQueryParams(RequestParameters):
    # Use OrderingQueryParams instead for more flexible ordering
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
                msg = f"We do not support ordering by provided field '{v}'. Fields supported are {msg_field_options}."
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


def _parse_order_by(v):
    if not v:
        return []

    # Pass through if already parsed (list of dicts or OrderClause instances)
    if isinstance(v, list):
        if all(isinstance(item, (dict, OrderClause)) for item in v):
            return v
        v = ",".join(str(item) for item in v)

    if not isinstance(v, str):
        msg = "order_by must be a string"
        raise TypeError(msg)

    # 1. from comma-separated string to list of OrderClause
    clauses = []
    for t in v.split(","):
        token = t.strip()
        if not token:
            continue
        if token.startswith("-"):
            clauses.append((token[1:], OrderDirection.DESC))
        elif token.startswith("+"):
            clauses.append((token[1:], OrderDirection.ASC))
        else:
            clauses.append((token, OrderDirection.ASC))

    # 2. check for duplicates and conflicting directions
    return [{"field": field, "direction": direction} for field, direction in check_ordering_list(clauses)]


class OrderingQueryParams(BaseModel, Generic[TField]):  # noqa: UP046
    """
    This class is designed to parse query parameters for ordering results in an API request.

    It supports multiple ordering clauses and allows for flexible sorting options.

    NOTE: It only parses strings and validates into list[OrderClause[TField]]
    where TField is a type variable representing valid field names.


    For example:

        /my/path?order_by=field1,-field2,+field3

    would sort by field1 ascending, field2 descending, and field3 ascending.

    Subclasses can configure:
        _default_order_by: ClassVar[str] — default ordering string (e.g., "-modified_at")
        _field_name_map: ClassVar[dict[str, str]] — remap API field names to DB column names

    Example:
        class FolderOrdering(OrderingQueryParams[Literal["modified_at", "name"]]):
            _default_order_by: ClassVar[str] = "-modified_at"
            _field_name_map: ClassVar[dict[str, str]] = {"modified_at": "modified"}
    """

    _default_order_by: ClassVar[str] = ""
    _field_name_map: ClassVar[dict[str, str]] = {}

    order_by: Annotated[
        list[OrderClause[TField]],
        BeforeValidator(_parse_order_by),
        Field(
            description="Comma-separated list of field names with optional direction prefix (+ for asc, - for desc).",
            json_schema_extra={
                "examples": [
                    "-created_at,name,+gender",
                    "name",
                    "-modified_at",
                    "",
                ],
            },
        ),
    ] = ""  # type: ignore[assignment]

    model_config = ConfigDict(
        validate_default=True,
        json_schema_extra={
            "examples": [
                {"order_by": "-created_at,name,+gender"},
                {"order_by": ""},
            ],
        },
    )

    @model_validator(mode="before")
    @classmethod
    def _inject_default_order_by(cls, data: Any) -> Any:
        if isinstance(data, dict) and "order_by" not in data and cls._default_order_by:
            return {**data, "order_by": cls._default_order_by}
        return data

    @model_validator(mode="after")
    def _apply_field_name_map(self) -> "OrderingQueryParams[TField]":
        if self._field_name_map:
            for clause in self.order_by:
                mapped = self._field_name_map.get(str(clause.field))
                if mapped is not None:
                    clause.field = cast(TField, mapped)
        return self
