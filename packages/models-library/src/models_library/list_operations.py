"""List operation models and helpers

- Ordering: https://google.aip.dev/132#ordering


"""

from enum import Enum
from typing import TYPE_CHECKING, Annotated, Generic, TypeVar

from annotated_types import doc
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


class OrderClause(GenericModel, Generic[TField]):
    field: TField
    direction: OrderDirection = OrderDirection.ASC


def check_ordering_list(
    order_by: Annotated[
        list[tuple[TField, OrderDirection]],
        doc(
            "Duplicates with same direction dropped, conflicting directions raise ValueError"
        ),
    ],
) -> Annotated[
    list[tuple[TField, OrderDirection]],
    doc("Duplicates removed, preserving first occurrence order"),
]:
    """Validates ordering list and removes duplicate entries.

    Raises:
        ValueError: If a field appears with conflicting directions
    """
    seen_fields: dict[TField, OrderDirection] = {}
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
