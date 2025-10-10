from typing import Annotated, Generic, TypeVar

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import BaseModel, BeforeValidator, Field, TypeAdapter

ResourceT = TypeVar("ResourceT")
IdentifierT = TypeVar("IdentifierT")
SchemaT = TypeVar("SchemaT")


def _deduplicate_preserving_order(identifiers: list[IdentifierT]) -> list[IdentifierT]:
    """Remove duplicates while preserving order of first occurrence."""
    return list(dict.fromkeys(identifiers))


def create_batch_ids_validator(identifier_type: type[IdentifierT]) -> TypeAdapter:
    """Create a TypeAdapter for validating batch identifiers.

    This validator ensures:
    - At least one identifier is provided (empty list is invalid for batch operations)
    - Duplicates are removed while preserving order

    Args:
        identifier_type: The type of identifiers in the batch

    Returns:
        TypeAdapter configured for the specific identifier type
    """
    return TypeAdapter(
        Annotated[
            list[identifier_type],  # type: ignore[valid-type]
            BeforeValidator(_deduplicate_preserving_order),
            Field(
                min_length=1,
                description="List of identifiers to batch process. Empty list is not allowed for batch operations.",
            ),
        ]
    )


class BatchGetEnvelope(BaseModel, Generic[ResourceT, IdentifierT]):
    """Generic envelope model for batch-get operations that can contain partial results.

    This model represents the result of a batch operation where some items might be found
    and others might be missing. It enforces that at least one item must be found,
    as an empty batch operation is considered a client error.
    """

    found_items: Annotated[
        list[ResourceT],
        Field(
            min_length=1,
            description="List of successfully retrieved items. Must contain at least one item.",
        ),
    ]
    missing_identifiers: Annotated[
        list[IdentifierT],
        Field(
            default_factory=list,
            description="List of identifiers for items that were not found",
        ),
    ] = DEFAULT_FACTORY
