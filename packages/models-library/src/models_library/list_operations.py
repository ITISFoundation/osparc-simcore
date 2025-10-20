"""List operation models and helpers

- Ordering: https://google.aip.dev/132#ordering


"""

from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar, get_args, get_origin

from pydantic.generics import GenericModel


class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


if TYPE_CHECKING:
    from typing import Protocol

    class LiteralField(Protocol):
        """Protocol for Literal string types"""

        def __str__(self) -> str: ...

    TField = TypeVar("TField", bound=LiteralField)
else:
    TField = TypeVar("TField", bound=str)


def get_literal_values(tfield: Any) -> tuple[str, ...] | None:
    """Return Literal values if TField is a Literal, else None."""
    if get_origin(tfield) is Literal:
        return get_args(tfield)
    return None


class OrderClause(GenericModel, Generic[TField]):
    field: TField
    direction: OrderDirection = OrderDirection.ASC


def check_ordering_list(
    order_by: list[tuple[TField, OrderDirection]],
) -> list[tuple[TField, OrderDirection]]:
    """Validates ordering list and removes duplicate entries.

    Ensures that each field appears at most once. If a field is repeated:
    - With the same direction: silently drops the duplicate
    - With different directions: raises ValueError


    Args:
        order_by: List of (field, direction) tuples

    Returns:
        List with duplicates removed, preserving order of first occurrence

    Raises:
        ValueError: If a field appears with conflicting directions
    """
    seen_fields = {}
    unique_order_by = []

    for field, direction in order_by:
        if field in seen_fields:
            # Field already seen - check if direction matches
            if seen_fields[field] != direction:
                msg = f"Field '{field}' appears with conflicting directions: {seen_fields[field].value} and {direction.value}"
                raise ValueError(msg)
            # Same field and direction - skip duplicate
            continue

        # First time seeing this field
        seen_fields[field] = direction
        unique_order_by.append((field, direction))

    return unique_order_by


def map_order_fields(
    order_clauses: list[OrderClause[TField]], field_mapping: dict[str, str]
) -> list[tuple[str, OrderDirection]]:
    """Map order clause fields using a field mapping dictionary.

    Args:
        order_clauses: List of OrderClause objects with API field names
        field_mapping: Dictionary mapping API field names to domain/DB field names

    Returns:
        List of tuples with mapped field names and directions

    Example:
        >>> clauses = [OrderClause(field="email", direction=OrderDirection.ASC)]
        >>> mapping = {"email": "user_email", "created_at": "created"}
        >>> map_order_fields(clauses, mapping)
        [("user_email", OrderDirection.ASC)]
    """
    return [
        (field_mapping[str(clause.field)], clause.direction) for clause in order_clauses
    ]


def validate_order_fields_with_literals(
    order_by: list[tuple[str, str]],
    valid_fields: set[str],
) -> None:
    """Validate order_by list with string field names and directions.

    Args:
        order_by: List of (field_name, direction) tuples with string values
        valid_fields: Set of allowed field names
        valid_directions: Set of allowed direction values

    Raises:
        ValueError: If any field or direction is invalid
    """
    valid_directions = {OrderDirection.ASC.value, OrderDirection.DESC.value}

    invalid_fields = {field for field, _ in order_by if field not in valid_fields}
    if invalid_fields:
        msg = f"Invalid order_by field(s): {invalid_fields}. Valid fields are: {valid_fields}"
        raise ValueError(msg)

    invalid_directions = {
        direction for _, direction in order_by if direction not in valid_directions
    }
    if invalid_directions:
        msg = f"Invalid order direction(s): {invalid_directions}. Must be one of: {valid_directions}"
        raise ValueError(msg)
