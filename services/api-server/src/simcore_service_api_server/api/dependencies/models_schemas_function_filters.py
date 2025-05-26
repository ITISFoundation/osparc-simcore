from typing import Annotated

from fastapi import Query
from models_library.functions import FunctionIDString, FunctionJobCollectionsListFilters

from ._utils import _get_query_params


def get_function_job_collections_filters(
    # pylint: disable=unsubscriptable-object
    has_function_id: Annotated[
        FunctionIDString | None,
        Query(
            **_get_query_params(
                FunctionJobCollectionsListFilters.model_fields["has_function_id"]
            )
        ),
    ] = None,
) -> FunctionJobCollectionsListFilters:
    return FunctionJobCollectionsListFilters(
        has_function_id=has_function_id,
    )
