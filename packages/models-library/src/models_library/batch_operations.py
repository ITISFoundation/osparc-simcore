"""

# Batch Operations Rationale:

Please preserve the following behaviors when implementing batch operations:

| Case           | Behavior                                   | Justification               |
| -------------- | ------------------------------------------ | --------------------------- |
| Empty `names`  | `400 Bad Request`                          | Invalid input               |
| Some missing   | `200 OK`, with `missing` field             | Partial success             |
| Duplicates     | Silently deduplicate                       | Idempotent, client-friendly |
| Response order | Preserve request order (excluding missing) | Deterministic, ergonomic    |


- `BatchGet` is semantically distinct from `List`.
  - `List` means “give me everything you have, maybe filtered.”
  - `BatchGet` means “give me these specific known resources.”
- Passing an empty list means you’re not actually identifying anything to fetch — so it’s a client error (bad request), not a legitimate “empty result.”
- This aligns with the principle: If the request parameters are syntactically valid but semantically meaningless, return 400 Bad Request.

# References:
    - https://google.aip.dev/130
    - https://google.aip.dev/231
"""

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


class BatchCreateEnvelope(BaseModel, Generic[SchemaT]):
    """Generic envelope model for batch-create operations.

    This model represents the result of a strict batch create operation,
    containing the list of created items. The operation is expected to be "strict"
    in the sense that it either creates all requested items or fails entirely.
    """

    created_items: Annotated[
        list[SchemaT],
        Field(
            min_length=1,
            description="List of successfully created items",
        ),
    ]


class BatchUpdateEnvelope(BaseModel, Generic[SchemaT]):
    """Generic envelope model for batch-update operations.

    This model represents the result of a strict batch update operation,
    containing the list of updated items. The operation is expected to be "strict"
    in the sense that it either updates all requested items or fails entirely. See https://google.aip.dev/234
    """

    updated_items: Annotated[
        list[SchemaT],
        Field(
            min_length=1,
            description="List of successfully updated items",
        ),
    ]
