from enum import Enum
from typing import Any, TypedDict, get_args

import sqlalchemy as sa


class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class OrderByDict(TypedDict):
    field: str
    direction: OrderDirection


def create_ordering_clauses(
    order_by: list[OrderByDict],
    column_map: dict[str, Any],
) -> list[Any]:
    """Converts a list of ordering dicts into SQLAlchemy ordering clauses.

    Raises:
        ValueError: If a field in order_by is not found in column_map
    """
    clauses: list[Any] = []
    for item in order_by:
        field = item["field"]
        direction = item["direction"]

        column = column_map.get(field)
        if column is None:
            msg = f"Unknown ordering field '{field}'. Available fields: {', '.join(sorted(column_map))}"
            raise ValueError(msg)

        if direction == OrderDirection.DESC:
            clauses.append(sa.desc(column))
        else:
            clauses.append(sa.asc(column))
    return clauses


def assert_literal_keys_match_column_map(
    literal_type: type,
    column_map: dict[str, Any],
) -> None:
    """Asserts that every field in a Literal type has a matching key in the column map.

    Use in tests to verify that the API field names (Literal type args)
    are all covered by the repository column map.

    Raises:
        AssertionError: If there is a mismatch between Literal fields and column map keys
    """
    literal_fields = set(get_args(literal_type))
    map_keys = set(column_map)

    missing_from_map = literal_fields - map_keys
    extra_in_map = map_keys - literal_fields

    errors = []
    if missing_from_map:
        errors.append(f"Literal fields missing from column_map: {sorted(missing_from_map)}")
    if extra_in_map:
        errors.append(f"column_map keys not in Literal type: {sorted(extra_in_map)}")
    if errors:
        msg = "; ".join(errors)
        raise AssertionError(msg)
