from typing import Annotated

from fastapi import Query
from models_library.functions import (
    FunctionID,
    FunctionIDString,
    FunctionJobCollectionID,
    FunctionJobCollectionsListFilters,
    FunctionJobID,
)
from simcore_service_api_server.models.schemas.functions_filters import (
    FunctionJobsListFilters,
)

from ._utils import get_query_params


def get_function_job_collections_filters(
    # pylint: disable=unsubscriptable-object
    has_function_id: Annotated[
        FunctionIDString | None,
        Query(
            **get_query_params(
                FunctionJobCollectionsListFilters.model_fields["has_function_id"]
            )
        ),
    ] = None,
) -> FunctionJobCollectionsListFilters:
    return FunctionJobCollectionsListFilters(
        has_function_id=has_function_id,
    )


def get_function_jobs_filters(
    # pylint: disable=unsubscriptable-object
    function_id: Annotated[
        FunctionID | None,
        Query(**get_query_params(FunctionJobsListFilters.model_fields["function_id"])),
    ] = None,
    function_job_ids: Annotated[
        list[FunctionJobID] | None,
        Query(
            **get_query_params(FunctionJobsListFilters.model_fields["function_job_ids"])
        ),
    ] = None,
    function_job_collection_id: Annotated[
        FunctionJobCollectionID | None,
        Query(
            **get_query_params(
                FunctionJobsListFilters.model_fields["function_job_collection_id"]
            )
        ),
    ] = None,
) -> FunctionJobsListFilters:
    return FunctionJobsListFilters(
        function_id=function_id,
        function_job_ids=function_job_ids,
        function_job_collection_id=function_job_collection_id,
    )
