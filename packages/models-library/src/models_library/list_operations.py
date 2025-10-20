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
