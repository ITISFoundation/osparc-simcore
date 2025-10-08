from typing import Annotated, Generic, TypeVar

from common_library.basic_types import DEFAULT_FACTORY
from models_library.api_schemas_catalog.services import MyServiceGet
from models_library.services import ServiceKeyVersion
from pydantic import BaseModel, Field

R = TypeVar(
    "R"
    # Resource model type
)
ID = TypeVar(
    "ID"
    # Identifier model type
)


class BatchGetResult(BaseModel, Generic[R, ID]):
    """Generic model for batch-get operations that can contain partial results.

    In a batch-get operation, passing an empty list means you're not actually identifying anything to
    fetch — so it's a client error (bad request), not a legitimate “empty result.”
    """

    items: Annotated[
        list[R], Field(min_length=1, description="List of successfully retrieved items")
    ]
    missing: Annotated[
        list[ID],
        Field(
            default_factory=list,
            description="List of ids of the items that were not found",
        ),
    ] = DEFAULT_FACTORY


class BatchGetUserServicesResult(BatchGetResult[MyServiceGet, ServiceKeyVersion]):
    """Specialized batch result for user services operations."""
