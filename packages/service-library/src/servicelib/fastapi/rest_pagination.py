from typing import TypeAlias, TypeVar

from fastapi import Query
from fastapi_pagination.cursor import CursorPage
from fastapi_pagination.customization import (
    CustomizedPage,
    UseParamsFields,
)
from models_library.api_schemas_storage.storage_schemas import (
    DEFAULT_NUMBER_OF_PATHS_PER_PAGE,
    MAX_NUMBER_OF_PATHS_PER_PAGE,
)

_T = TypeVar("_T")

CustomizedPathsCursorPage = CustomizedPage[
    CursorPage[_T],
    # Customizes the maximum value to fit frontend needs
    UseParamsFields(
        size=Query(
            DEFAULT_NUMBER_OF_PATHS_PER_PAGE,
            ge=1,
            le=MAX_NUMBER_OF_PATHS_PER_PAGE,
            description="Page size",
        )
    ),
]
CustomizedPathsCursorPageParams: TypeAlias = CustomizedPathsCursorPage.__params_type__  # type: ignore
